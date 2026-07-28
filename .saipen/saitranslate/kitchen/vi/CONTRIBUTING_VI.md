# Đóng góp cho SAIPEN

SAIPEN trước hết là một đặc tả, sau đó mới là một bản triển khai. Hầu hết các đóng góp
là những thay đổi đối với `saipen/RFC.md`, một tệp `phases/*.md`, hoặc các công cụ
tuân thủ trong `tests/` -- không phải mã ứng dụng.

## Trước khi đề xuất thay đổi

Hãy chạy [Phép thử SAIPEN](SPEC.md#the-saipen-litmus-test) với
ý tưởng của bạn:
1. Nó có làm cho quá trình chuyển đổi giữa các agent đáng tin cậy hơn không?
2. Nó có làm cho hành vi của các mô hình khác nhau trở nên đồng nhất hơn không?
3. Nó có giảm xác suất mất ngữ cảnh không?

Nếu câu trả lời là "không" cho ít nhất hai trong số các câu hỏi trên, thì nó nằm ngoài phạm vi của
giao thức này, bất kể nó có thể hữu ích như thế nào ở nơi khác.

## Báo cáo lỗ hổng

Hãy mở một issue mô tả:
- lỗ hổng nằm ở tệp/phần nào (RFC.md, tài liệu giai đoạn (phase doc), lược đồ, bài kiểm thử)
- bằng chứng cụ thể (một đoạn trích dẫn, một lệnh và kết quả của nó, một kịch bản nơi
  hành vi hiện tại bị phá vỡ)
- những gì bạn mong đợi thay vì vậy

Các báo cáo mơ hồ ("cái này cảm giác không ổn") khó hành động hơn một lệnh
`grep`/tái tạo cụ thể. Xem mẫu báo cáo lỗi (bug report issue template) để biết định dạng mà nó
nên có.

## Thực hiện thay đổi

1. Đọc đầy đủ `saipen/RFC.md` và (các) tệp `phases/*.md` có liên quan trước khi
   chỉnh sửa -- hầu hết những khoảng trống dường như đã được giải quyết ở nơi khác,
   hoặc cố ý được xác định theo một cách nhất định vì một lý do có tài liệu chứng minh.
2. Kiểm tra `CHANGELOG.md` và `.saipen/KNOWLEDGE/decisions.md` để xem các kỹ thuật/quyết định trước đó (prior art).
   Đừng âm thầm mở lại một quyết định đã được đưa ra và bị từ chối --
   nếu bạn có bằng chứng mới cho thấy một sự từ chối trước đó là sai, hãy nói rõ
   trong phần mô tả PR.
3. Mỗi sự thay đổi mang tính quy chuẩn (một MUST/MUST NOT/SHOULD) đều cần một mục
   `CHANGELOG.md` và, nếu có thể thực hiện, phạm vi phủ sóng trong `tests/validate.sh` +
   `tests/validate.ps1` (cả hai nền tảng) hoặc một vật cố định (fixture) dưới
   `tests/scenarios/`.
4. Chạy trình xác thực chuẩn (canonical validator) trước khi mở một PR:
   ```bash
   python tools/validate.py
   ```
   Đây mới là thứ quan trọng – nó kiểm tra `STATE.md` so với
   `extensions/schemas/state.schema.json`, duyệt đồ thị sự kiện `LOG.md`
   qua các phân đoạn đã niêm phong và xác minh runtime manifest và injector
   wiring. `tests/validate.sh` / `validate.ps1` là **mức sàn di động đông
   lạnh** cho các máy chủ không có Python (chúng nói như vậy ở đầu mỗi tệp):
   ít kiểm tra hơn, chỉ giữ lại để máy chủ không có Python không bị bỏ lại
   tay không. Chạy chúng nữa nếu thay đổi của bạn chạm vào một trong hai
   tệp đó, nhưng đừng bao giờ *thay thế* -- chỉ vượt qua mức sàn chứng minh
   được ít hơn nhiều so với vẻ ngoài của nó. CI chạy trình xác thực chuẩn
   trên mọi push và PR bất kể thế nào (`.github/workflows/validate.yml`).
5. Tăng phiên bản `VERSION` theo sơ đồ trong `phases/ship.md` (patch cho các 
   làm rõ chỉ thuộc về tài liệu, minor cho hành vi quy chuẩn mới, major cho các thay đổi
   phá vỡ hợp đồng (breaking changes)) và giữ huy hiệu phiên bản của `README.md` đồng bộ --
   `tests/validate.sh`/`.ps1` kiểm tra điều này tự động khi được chạy từ một
   bản sao của repo này.

## Phong cách

- Tài liệu Giao thức và các giai đoạn: ngắn gọn, sử dụng các từ khóa RFC-2119 ở những nơi chúng quan trọng, không có
  từ ngữ thừa thãi. Xem `saipen/STYLE.md`.
- Mọi thứ trong tệp này, thông báo commit, chú thích mã, và
  CHANGELOG: đơn giản và chuyên nghiệp. Các giọng điệu chat/LOG riêng của dự án
  (`saipen/STYLE.md`) không áp dụng cho các artifacts (tài liệu/kết quả công việc).

## Những gì nằm ngoài phạm vi

- Biến SAIPEN thành một hệ thống đồng thuận phân tán. Xem
  phần Ranh giới Phân tán & Đồng thời của `SPEC.md`.
- Ngữ pháp đánh dấu LOG có thể phân tích bằng máy (machine-parseable) vượt quá bộ khung hiện có.
  `LOG.md` vẫn giữ văn xuôi xung quanh một hình dạng cố định.
- Lệnh `saipen doctor` hoặc lệnh dư thừa tương tự với `saipen validate` +
  `saipen status`.

Mỗi vấn đề này đều đã được đề xuất và đánh giá trước đây; việc mở lại chúng cần
bằng chứng mới, không phải chỉ hỏi lại.
