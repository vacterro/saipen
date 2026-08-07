<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Hướng dẫn SAIPEN (Tiếng Việt)

[TRANSLATED VI]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## Khởi đầu nhanh

## Lệnh

## Điều nên biết
- Có thay đổi chưa commit khi quay lại dự án? Bình thường thôi -- SAIPEN chỉ commit ở bước `ship`, không phải mỗi bước. Agent sẽ kiểm tra xem đó là thay đổi của ai trước khi động vào bất cứ thứ gì.
- Muốn nó nhớ một quyết định kiến trúc thực sự? Đặt vào `.saipen/KNOWLEDGE/`, dưới dạng một file `decisions.md` hoặc các file đánh số `ADR-001.md`.
- Máy này không có git hay shell? Agent sẽ nói thẳng (`mode`, `WAIT: <category> -- <câu hỏi>`) thay vì đoán mò (danh mục là một trong bảy: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; nó cho biết loại câu trả lời nào mở khóa tình huống)
- Muốn có lưới an toàn? `python <saipen-clone>/tools/install_hook.py` sẽ cài đặt kiểm tra trước khi commit.