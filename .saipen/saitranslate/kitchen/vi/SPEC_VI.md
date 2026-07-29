# Đặc tả SAIPEN

## Tóm tắt
**Mục tiêu Thiết kế #1: Một agent mới khởi động không có lịch sử trò chuyện phải có khả năng thực thi `/saipen continue` và tiếp tục công việc hiệu quả trong vòng một phút, mà không yêu cầu người dùng lặp lại ngữ cảnh.**

SAIPEN đảm bảo rằng bất kỳ AI agent tương thích nào cũng có thể tiếp tục an toàn bất kỳ dự án nào mà không cần được giao việc lại. Nó là một ABI (Application Binary Interface) cho các AI agent lập trình—một lớp tương thích giải quyết vấn đề mất trí nhớ. Cho dù bạn sử dụng Claude hôm nay, Gemini ngày mai, và GPT ngày mốt, tất cả chúng sẽ hoạt động trên cùng một trạng thái dự án mà không yêu cầu bạn nhắc lại ngữ cảnh.

### Triết lý cốt lõi: Trạng thái Dự án > Bộ nhớ Mô hình
Bộ nhớ nên sống bên cạnh mã nguồn, không phải bên trong đầu của một mô hình khác. SAIPEN chuyển đổi mô hình từ `Project -> Memory -> LLM` thành `Project -> SAIPEN State -> LLM`. Bộ nhớ thuộc về dự án.

Về cốt lõi, SAIPEN sử dụng một giao thức tiếp tục dựa trên tệp, di động cho các LLM agent. Các triển khai CÓ THỂ khác nhau. Hợp đồng trên đĩa PHẢI duy trì ổn định. Mọi thứ trong giao thức này tồn tại để phục vụ Bài kiểm tra Tiếp tục (Continuation Test).

SAIPEN mang tính tiến hóa, không mang tính sáng tạo. Mục đích của nó là hoàn thiện phần mềm, không phải phát minh lại nó. ADD mở rộng các mẫu thiết kế hiện có, các quy ước ngành, và tính đối xứng tính năng rõ ràng.

- **`STATE`**: Tồn tại để trả lời *"Hiện tại tôi cần làm gì?"*
- **`BOARD`**: Tồn tại để trả lời *"Tôi đang nhận nhiệm vụ nào?"*
- **`LOG`**: Tồn tại để trả lời *"Tại sao chúng ta lại đi đến điểm này?"*
- **`KNOWLEDGE`**: Tồn tại để trả lời *"Sự thật bền vững của dự án này là gì?"*
- **`next_action`**: Trái tim của SAIPEN. Nó trả lời *"Lệnh chính xác nào tôi cần thực thi ngay giây phút này để tiếp tục công việc?"*

## Phép thử SAIPEN

Bất kỳ thay đổi hoặc ý tưởng mới nào được đề xuất cho giao thức PHẢI vượt qua ba câu hỏi sau:
1. Nó có làm cho quá trình chuyển đổi giữa các agent đáng tin cậy hơn không?
2. Nó có làm cho hành vi của các mô hình khác nhau trở nên đồng nhất hơn không?
3. Nó có giảm xác suất mất ngữ cảnh không?

Nếu câu trả lời là "không" cho ít nhất hai trong số những câu hỏi này, ý tưởng sẽ bị từ chối. SAIPEN ưu tiên kỷ luật, khả năng tái tạo và độ tin cậy hơn là sự mới mẻ.

## Kiến trúc

Giao thức mang tính quy chuẩn nghiêm ngặt. SAIPEN chia tách khái niệm thành hai lớp: **Core** (Cốt lõi) và **Maintenance** (Bảo trì).
- **Lớp Core** đảm bảo việc tiếp tục tác vụ an toàn, trung lập với nhà cung cấp.
- **Lớp Maintenance** là một mô hình tiến hóa phần mềm tự trị được xây dựng dựa trên lớp Core.

Bên dưới hai lớp này, SAIPEN tách biệt ba mối quan tâm không bao giờ đan xen:
**tính đúng đắn và sự tiếp tục** (Core -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, đàm phán khả năng,
checkpointing), **sự tiến hóa không giám sát** (Maintenance -- `HUNT`/`ADD`/`CLEAN`,
đầy đủ chức năng dưới mặc định thuần túy `saipen`/`saipen continue`), và **thông lượng**
(Goal Mode, Subagents -- cả hai đều phải chọn tham gia rõ ràng, §1.3/§2.4). Vô hiệu hóa Chế độ Mục tiêu (Goal Mode):
giao thức không thay đổi, mỗi lần một vé. Vô hiệu hóa Subagents: `HUNT` chạy cùng
sáu danh mục tuần tự, cùng kết quả. Chỉ sử dụng Core, không có lớp Maintenance
nào cả: nó vẫn giữ nguyên -- một agent mới khởi động vẫn tiếp tục một cách chính xác. Mỗi lớp xây dựng trên
lớp bên dưới mà không bao giờ có trường hợp ngược lại; không có cái gì ngược dòng phụ thuộc vào một
tính năng xuôi dòng hiện có.

```text
saipen/
  RFC.md                    đặc tả quy chuẩn (chia thành Core và Maintenance)
  CONFORMANCE.md             vector tự kiểm tra + bảng phạm vi kịch bản
  SKILL.md                  điểm truy cập mỏng cho các nền tảng đọc skill
  STYLE.md                  giọng điệu: trò chuyện, LOG.md, artifacts
  UI.md                     đặc tả UI Vintage Golden (bắt buộc cho công việc UI)
  BOOT.md                   ~nhân khởi động nguội: đường dẫn nhanh mà bare `continue`
                             cần, trước khi bất kỳ thứ nào ở trên được tải
  phases/                   logic máy trạng thái nghiêm ngặt -- 16 tài liệu, một tài
                             liệu cho mỗi giá trị enum RFC § 1.6 (được máy kiểm tra
                             cả hai chiều bởi tools/validate.py)
    [Core Phases]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Maintenance Phases]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastructure]
    prepare.md              đóng gói công việc để bàn giao cho agent tiếp theo
    validate.md             kiểm thử tuân thủ

extensions/                 <- LỚP THÍCH ỨNG
  adapters/                 các cầu nối hướng dẫn theo từng mô hình, cho các nền tảng mà
                             trình tiêm không tự động phát hiện (README.md chỉ đến đây)
  schemas/                  state.schema.json được đọc bằng máy bởi tools/validate.py
                             (nguồn sự thật duy nhất cho hình dạng của STATE); schemas cho board/log
                             chỉ mang tính chất tham khảo (xem schemas/README.md)
  templates/                bản soạn sẵn .saipen/ mới
  security/                 VÍ DỤ hook sao chép vào một dự án (RFC § 1.9, gắn vào VERIFY)
  performance/              VÍ DỤ hook sao chép vào một dự án (RFC § 1.9, gắn vào REVIEW)
  subs/                     VÍ DỤ các subagent nghiên cứu chỉ-đọc (RFC § 1.9) -- có
                             STATE/BOARD/LOG riêng mỗi subagent, các phát hiện chỉ qua OUTBOX,
                             không bao giờ là con đường ghi thứ hai vào dự án

bootstrap/                  <- CÀI ĐẶT/XUẤT/GỠ CÀI ĐẶT, mỗi lần một máy
  inject.ps1 / .sh          cài đặt khối SAIPEN + bản sao skill (README Bắt đầu nhanh)
  uninstall.ps1 / .sh       đảo ngược quá trình tiêm -- xóa khối + bản sao skill
  export.ps1 / .sh          lưu trữ thư mục .saipen/ của một dự án để sao lưu
  saipen_crew.bat / .sh     mở bố cục crew 3 cửa sổ (phần thưởng, extensions/subs/crew.md)

tools/                      <- TRÌNH XÁC THỰC CHÍNH THỨC & TIỆN ÍCH REPO
  validate.py               trình xác thực tuân thủ chính thức (stdlib Python, không
                             cài đặt thêm; xác thực STATE dựa trên state.schema.json
                             trực tiếp, cộng với kiểm tra đồ thị mà cặp shell không thể làm)
  install_hook.py           cài đặt một pre-commit hook chạy validate.py
  uninstall_hook.py         xóa chính xác hook đó (khôi phục lại mọi hook trước đó)

tests/                      <- LỚP TUÂN THỦ
  validate.ps1 / .sh        cơ sở di động bị đóng băng cho các máy chủ không có Python --
                             các kiểm tra mới chỉ cập bến trong tools/validate.py
  scenarios/                các trạng thái giả (phục hồi sau sự cố, xung đột xác nhận quyền, v.v.)
```

## Đàm phán Khả năng Hai chiều
Các agent không chỉ đơn giản tuyên bố những gì chúng có thể làm; giao thức đòi hỏi những gì được yêu cầu.
Dự án định nghĩa `requires: [filesystem, git, shell, python]` trong trạng thái của nó. Agent đối chiếu chéo các khả năng của máy chủ và khóa vào một `mode` (ví dụ: `full`, `read-only`).

## Ghi nhật ký Sự kiện Dựa trên Đồ thị
Nhật ký trong SAIPEN không phải là các chuỗi tuyến tính. Chúng tạo thành một đồ thị quyết định có hướng không tuần hoàn sử dụng ID sự kiện (`E-001`). Điều này cho phép phân nhánh phức tạp, hợp nhất agent, và các dấu vết kiểm toán chính xác.

## Hồ sơ Quyết định Kiến trúc (ADR)
Các nhật ký sự kiện tạm thời không lưu trữ kiến thức vĩnh viễn. SAIPEN bắt buộc rằng các quyết định kiến trúc mang tính cấu trúc được lưu trữ dưới dạng các ADR (ví dụ: `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Ranh giới Phân tán & Đồng thời
SAIPEN đảm bảo tính toàn vẹn trạng thái thông qua các xác nhận dựa trên tệp (`owner`, `claim_time`) và các đồ thị tuần tự (`LOG.md`). Tuy nhiên, **SAIPEN là một giao thức trạng thái, không phải là một thuật toán đồng thuận phân tán.**
- **Hệ thống Tệp Cục bộ/Chia sẻ**: Việc giải quyết xung đột dựa trên các lần ghi hệ thống tệp nguyên tử ("commit đầu tiên thắng").
- **Môi trường Phân tán/Mạng**: Nếu các agent hoạt động trên các máy bị ngắt kết nối mà không đồng bộ tệp theo thời gian thực, các điều kiện đua trên các xác nhận của `BOARD.md` sẽ xảy ra. Trong các thiết lập phân tán cao độ, hợp đồng giao thức trên đĩa của SAIPEN PHẢI duy trì ổn định -- chính trạng thái dự án vẫn liên tục biến đổi, thông qua các quy tắc riêng của SAIPEN (§ 1.5 checkpointing), không bao giờ là hình dạng giao thức mà các quy tắc đó tuân theo.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
