# Chính sách Bảo mật

## Phạm vi

SAIPEN là một đặc tả cộng với một bộ nhỏ các tập lệnh cài đặt/xuất cục bộ
(`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`,
`export.ps1`/`.sh`). Nó không chạy một máy chủ, không thu thập
đo từ xa (telemetry), và không truyền bất kỳ dữ liệu nào đến bất cứ đâu. Mọi thứ các
tập lệnh làm là ghi hệ thống tệp cục bộ vào các tệp bạn đã kiểm soát
(`~/.claude`, `~/.gemini`, thư mục `.saipen/` dự án của bạn, v.v.).

Hai mức độ cẩn trọng khác nhau được áp dụng ở đây, và việc chính xác
sẽ tốt hơn là tuyên bố an toàn một cách chung chung:

- **Các tệp cấu hình của riêng bạn** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.aider.conf.yml`) chỉ được chỉnh sửa bằng cách thêm hoặc xóa một
  khối có ranh giới `SAIPEN:BEGIN`/`END`, và bản gốc được sao chép sang
  `<file>.bak` trước lần sửa đổi đầu tiên. Gỡ cài đặt sẽ ghi thêm
  `<file>.uninstalled.bak` trước khi xóa.
- **Các thư mục kỹ năng (skill)** mà trình tiêm tạo (`~/.claude/skills/saipen`
  và tương tự) là các bản sao thuộc sở hữu của SAIPEN và **không được** sao lưu:
  cài đặt ghi đè chúng hàng loạt và gỡ cài đặt xóa chúng đệ quy. Điều đó
  có chủ đích -- chúng chỉ chứa các bản sao của chính tệp của repo này --
  nhưng nếu bạn tự chỉnh sửa bản sao kỹ năng cục bộ, các chỉnh sửa đó sẽ bị mất
  trong lần `inject`/`uninstall` tiếp theo. Giữ các tùy chỉnh trong khối cấu hình
  của riêng bạn hoặc một fork, không phải bên trong thư mục kỹ năng đã sao chép.

Hai điều thực sự đáng để báo cáo bảo mật:
1. Một tập lệnh khởi động làm điều gì đó với hệ thống tệp hoặc lịch sử git của bạn
   vượt ra ngoài những gì các bình luận/README của chính nó mô tả.
2. Quy tắc vệ sinh bí mật của chính giao thức (RFC.md § 1.1 -- không bao giờ ghi
   khóa API, token, mật khẩu vào `STATE.md`/`BOARD.md`/`LOG.md`/
   `KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/
   `recovery/`/`logs/`) thực sự có một lỗ hổng khiến một
   agent tuân theo SAIPEN rò rỉ một bí mật vào một tệp được commit. Hai cái cuối
   là những cái tinh vi: Recovery sao chép nguyên văn `STATE.md` bị hỏng vào
   `.saipen/recovery/`, và việc niêm phong LOG di chuyển nguyên văn các dòng vào
   `.saipen/logs/`, vì vậy bất cứ thứ gì đến được bản gốc đều được lưu trữ bởi
   cơ chế mà toàn bộ nhiệm vụ của chúng là không thay đổi nội dung.

## Các phiên bản được hỗ trợ

Chỉ bản phát hành được gắn thẻ (tagged) mới nhất trên `main` mới được hỗ trợ. Đây là một
đặc tả giao thức, không phải là một dịch vụ sống lâu -- không có nhánh LTS (Hỗ trợ Dài hạn).

## Báo cáo Lỗ hổng bảo mật

Hãy mở một GitHub issue. Nếu báo cáo liên quan đến một vấn đề thực tế, hiện tại có thể khai thác
(không phải một giả thuyết), hãy đánh dấu nó là private/security advisory (cố vấn bảo mật riêng tư) thông qua
tab **Security** của repository này ("Report a vulnerability") thay vì
một issue công khai, để nó không hiển thị công khai trước khi có bản sửa lỗi.

Bao gồm: tập lệnh hoặc quy tắc RFC nào, kịch bản cụ thể, và những gì
thực sự xảy ra so với những gì lẽ ra phải xảy ra. Cùng một tiêu chuẩn bằng chứng như bất kỳ
báo cáo lỗi nào khác (xem `CONTRIBUTING.md`).
