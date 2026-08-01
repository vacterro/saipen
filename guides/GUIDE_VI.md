<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Hướng dẫn SAIPEN (Tiếng Việt)

SAIPEN là sổ ghi nhớ trong thư mục `.saipen/` cho các tác nhân AI.

**Phím tắt:** `cc` tiếp tục Goal Mode đang chạy, `sss` báo trạng thái mà không đụng vào mã và `ss` lưu điểm kiểm tra rồi dừng. [Xem bản đồ đầy đủ 11 phím](../saipen/RFC.md#110-command-surface). Các cặp song sinh Cyrillic cũng hoạt động: `сс`, `ссс`, `аа`, `ее`, `рр`.

## Khởi đầu nhanh

1. **Cài đặt một lần cho mỗi máy:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Khởi động dự án:**
> `saipen set`

3. **Làm việc:**
> `saipen`

## Lệnh

| Lệnh | Hành động |
|---|---|
| `saipen set` | Khởi tạo thư mục bộ nhớ `.saipen/` |
| `saipen continue` | Tiếp tục công việc từ ghi chú |
| `saipen stop` | Lưu tiến trình & dừng lại |
| `saipen status` | Đọc bảng & trạng thái |
| `saipen goal <text>` | Chuyển sang mục tiêu mới |
| `saipen clean` | Dọn dẹp sâu kho lưu trữ |
| `saipen translate` | Xây dựng bản dịch 32 ngôn ngữ cô lập |
| `saipen markhunt` | Kiểm tra sâu, không giới hạn -- chỉ ghi nhận, không sửa |
| `saipen prepare` | Đóng gói công việc để bàn giao cho agent tiếp theo |
| `saipen ship` | Kích hoạt quy trình phát hành |

## Điều nên biết
- Có thay đổi chưa commit khi quay lại dự án? Bình thường thôi -- SAIPEN chỉ commit ở bước `ship`, không phải mỗi bước. Agent sẽ kiểm tra xem đó là thay đổi của ai trước khi động vào bất cứ thứ gì.
- Muốn nó nhớ một quyết định kiến trúc thực sự? Đặt vào `.saipen/KNOWLEDGE/`, dưới dạng một file `decisions.md` hoặc các file đánh số `ADR-001.md`.
- Máy này không có git hay shell? Agent sẽ nói thẳng (`mode`, `WAIT: <category> -- <câu hỏi>`) thay vì đoán mò (danh mục là một trong bảy: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; nó cho biết loại câu trả lời nào mở khóa tình huống)
- Muốn có lưới an toàn? `python <saipen-clone>/tools/install_hook.py` sẽ cài đặt kiểm tra trước khi commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
