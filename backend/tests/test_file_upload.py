"""文件上传安全校验测试

覆盖四重校验：扩展名、MIME 类型、魔数、文件大小。
"""

from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.utils.security.file_upload import (
    _check_extension,
    _check_file_size,
    _check_magic_number,
    _check_mime_type,
    validate_upload_file,
)


def _make_upload_file(
    filename: str,
    content: bytes,
    content_type: str = "application/pdf",
) -> UploadFile:
    """构造 UploadFile 测试对象"""
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers={"content-type": content_type},
    )


class TestCheckExtension:
    """扩展名校验"""

    def test_valid_pdf(self):
        assert _check_extension("resume.pdf") is None

    def test_valid_docx(self):
        assert _check_extension("resume.docx") is None

    def test_valid_txt(self):
        assert _check_extension("resume.txt") is None

    def test_invalid_extension(self):
        result = _check_extension("resume.exe")
        assert result is not None
        assert "exe" in result

    def test_empty_filename(self):
        assert _check_extension("") == "文件名为空"

    def test_none_filename(self):
        assert _check_extension(None) == "文件名为空"

    def test_no_extension(self):
        result = _check_extension("resume")
        assert result is not None
        assert "不支持的文件扩展名" in result

    def test_case_insensitive(self):
        assert _check_extension("resume.PDF") is None
        assert _check_extension("resume.DOCX") is None


class TestCheckMimeType:
    """MIME 类型校验"""

    def test_valid_pdf_mime(self):
        assert _check_mime_type("application/pdf") is None

    def test_valid_docx_mime(self):
        assert _check_mime_type(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ) is None

    def test_valid_txt_mime(self):
        assert _check_mime_type("text/plain") is None

    def test_invalid_mime(self):
        result = _check_mime_type("application/x-executable")
        assert result is not None

    def test_none_mime(self):
        result = _check_mime_type(None)
        assert result is not None


class TestCheckMagicNumber:
    """魔数校验"""

    @pytest.mark.asyncio
    async def test_valid_pdf_magic(self):
        file = _make_upload_file("test.pdf", b"%PDF-1.5 rest of file")
        assert await _check_magic_number(file) is None

    @pytest.mark.asyncio
    async def test_valid_docx_magic(self):
        file = _make_upload_file("test.docx", b"PK\x03\x04 rest of file")
        assert await _check_magic_number(file) is None

    @pytest.mark.asyncio
    async def test_txt_skips_magic_check(self):
        file = _make_upload_file("test.txt", b"hello world")
        assert await _check_magic_number(file) is None

    @pytest.mark.asyncio
    async def test_invalid_magic(self):
        file = _make_upload_file("test.pdf", b"NOTAPDF content here")
        result = await _check_magic_number(file)
        assert result is not None
        assert "魔数校验失败" in result

    @pytest.mark.asyncio
    async def test_file_pointer_reset(self):
        """校验后文件指针应重置到开头"""
        content = b"%PDF-1.5 rest of file"
        file = _make_upload_file("test.pdf", content)
        await _check_magic_number(file)
        # UploadFile 没有 tell()，通过读取验证指针在开头
        reset_content = await file.read()
        assert reset_content == content


class TestCheckFileSize:
    """文件大小校验"""

    @pytest.mark.asyncio
    async def test_valid_size(self):
        file = _make_upload_file("test.pdf", b"%PDF-1.5 small file")
        assert await _check_file_size(file) is None

    @pytest.mark.asyncio
    async def test_empty_file(self):
        file = _make_upload_file("test.pdf", b"")
        result = await _check_file_size(file)
        assert result == "文件为空"

    @pytest.mark.asyncio
    async def test_oversized_file(self):
        """超过大小限制"""
        large_content = b"%PDF" + b"x" * (11 * 1024 * 1024)  # 11MB
        file = _make_upload_file("test.pdf", large_content)
        result = await _check_file_size(file)
        assert result is not None
        assert "超过限制" in result

    @pytest.mark.asyncio
    async def test_file_pointer_reset(self):
        content = b"%PDF-1.5 small file"
        file = _make_upload_file("test.pdf", content)
        await _check_file_size(file)
        # UploadFile 没有 tell()，通过读取验证指针在开头
        reset_content = await file.read()
        assert reset_content == content


class TestValidateUploadFile:
    """集成校验"""

    @pytest.mark.asyncio
    async def test_valid_pdf(self):
        file = _make_upload_file(
            "resume.pdf", b"%PDF-1.5 content", "application/pdf"
        )
        result = await validate_upload_file(file)
        assert result["valid"] is True
        assert result["filename"] == "resume.pdf"

    @pytest.mark.asyncio
    async def test_invalid_extension_raises(self):
        file = _make_upload_file(
            "resume.exe", b"\x4d\x5a content", "application/x-msdownload"
        )
        with pytest.raises(HTTPException) as exc_info:
            await validate_upload_file(file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_magic_mismatch_raises(self):
        """扩展名是 pdf 但内容不是 PDF"""
        file = _make_upload_file(
            "resume.pdf", b"FAKECONTENT", "application/pdf"
        )
        with pytest.raises(HTTPException) as exc_info:
            await validate_upload_file(file)
        assert exc_info.value.status_code == 400
