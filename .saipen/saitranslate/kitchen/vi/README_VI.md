<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**Giao thức tiếp nối cho các tác nhân lập trình AI.**Bộ nhớ dự án tồn tại ở dạng văn bản thường
tệp Markdown bên trong dự án(`.saipen/`), do đó bất kỳ tác nhân lạnh nào tương thích —
không có lịch sử trò chuyện, không có bộ nhớ phiên — đều có thể chạy`/saipen continue`, đọc
được lưu trữ`next_action`, và tiếp tục công việc mà không cần người dùng phải giải thích lại
bất cứ điều gì. Trạng thái thuộc về dự án, không thuộc về bộ nhớ của một nhà cung cấp mô hình nào.

**Một lệnh để tiếp tục. Trạng thái dạng tệp văn bản. Hợp đồng được kiểm tra bởi máy.**

Kho lưu trữ tự kiểm tra mình trên mỗi lần đẩy; cài đặt, trạng thái, kiểm tra và
gỡ cài đặt đều là cục bộ — không có dịch vụ đám mây, không có tiến trình nền, không có cơ sở dữ liệu.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.231.2** | [Thông số kỹ thuật](SPEC.md) | [Hướng dẫn](GUIDE.md) | [Lõi](saipen/CORE.md) | [Bảo trì](saipen/MAINTENANCE.md) | [Phong cách](saipen/STYLE.md) | [Giao diện người dùng](saipen/UI.md) | [Tuân thủ](saipen/CONFORMANCE.md) |MIT

**Phím tắt:** `cc` tiếp tục bối cảnh dự án đến hội tụ (tiếp tục mục tiêu đang chạy nếu có), `sss` báo trạng thái mà không đụng vào mã và `ss` lưu điểm kiểm tra rồi dừng. [Xem bản đồ đầy đủ 19 phím](saipen/RFC.md#110-command-surface). Các cặp song sinh Cyrillic cũng hoạt động: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## Điều gì còn tồn tại

Bộ nhớ dự án trực tiếp sống trong`.saipen/`— các tệp đơn giản bạn có thể đọc, so sánh và
cam kết bên cạnh mã. Một tác nhân lạnh trả lời năm câu hỏi từ các tệp
một mình:

|Tệp / trường|Câu trả lời|
|---|---|
| `STATE.md` |Điều gì đang xảy ra ngay bây giờ?(giai đoạn, vé đang hoạt động, chế độ vận hành, chướng ngại vật) |
| `BOARD.md` |Công việc nào hiện có / đang diễn ra?(đồ thị vé: ĐANG THỰC HIỆN, CHƯA LÀM, ĐÃ HOÀN THÀNH, BỊ CHẶN) |
| `LOG.md` |Tại sao dự án đạt đến trạng thái này?(đồ thị sự kiện chỉ thêm không xóa) |
| `KNOWLEDGE/` |Những sự thật bền vững nào của dự án phải tồn tại qua các phiên?|
| `next_action` (trong`STATE.md`) |Hành động cụ thể nào mà đại lý tiếp theo nên thực hiện?|

Đây là hợp đồng kiểm tra điểm, không phải là đề xuất thiết kế:`saipen stop`và mỗi
chuyển tiếp vé sẽ ghi các tệp theo một thứ tự cố định, và kết quả được kiểm tra bởi
một trình xác thực. Không có gì được lưu trữ trong cơ sở dữ liệu được lưu trữ, và không có gì bị mất khi
phiên làm việc kết thúc.

## Khởi động nhanh

**1. Cài đặt một lần cho mỗi máy**— dạy Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, và bất kỳ trình đọc nào`~/.agents/skills`thông thường(FreeBuff, v.v.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`khối lệnh gửi đến chỉ thị của tác nhân
các tệp bạn đã có(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— sao lưu từng tệp đến`.bak`trước tiên —
và sao chép giao thức vào các thư mục kỹ năng tương ứng. Không có gì nằm ngoài những thứ đó
đường dẫn, không có tiến trình nền, không có cuộc gọi mạng.</sub>

**2. Bắt đầu một dự án**— mở một tác nhân trong thư mục của bạn, nhập:

> `saipen set`

**Không cần cài đặt?**Dán một dòng vào bất kỳ tác nhân nào:

> Đọc&lt;clone&gt;/saipen/BOOT.md trước(hạt nhân khởi động lạnh), sau đó&lt;clone&gt;/saipen/INDEX.md +&lt;sao chép&gt;/saipen/STYLE.md và tuân theo chúng.

**Bạn đã thay đổi ý định?**Một lệnh sẽ đưa nó trở lại:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Nó xóa chính xác khối được đánh dấu(giữ lại phần còn lại của tệp của bạn), lưu lại
a `.uninstalled.bak`sao chép trước, và xóa các thư mục kỹ năng.

## Tại sao không chỉ sử dụng lịch sử trò chuyện?

SAIPEN nhắm đến một lỗi cụ thể: một tác nhân lập trình AI không nhớ điều gì cả
một khi phiên làm việc kết thúc. Các công cụ và thói quen khác giải quyết một phần vấn đề đó:

|Phương pháp|Điều gì nó tốt cho|Điều gì nó không mang theo|
|---|---|---|
|Lịch sử trò chuyện / bộ nhớ mô hình|Tiện lợi, không cần cài đặt|Phụ thuộc vào phiên và nhà cung cấp; không được lưu trữ cùng với dự án, vì vậy một tác nhân mới không bao giờ nhìn thấy nó|
|Tĩnh`AGENTS.md`Tập tin / hướng dẫn|Quy tắc và quy ước đứng vững|Không tự thân đại diện cho trạng thái nhiệm vụ sống,`next_action`, hoặc lịch sử phục hồi|
|Trình theo dõi vấn đề / TODO|Quản lý nhiệm vụ và danh sách công việc|Không tự bản thân xác định ngữ nghĩa tiếp tục của tác nhân — những gì tác nhân lạnh phải đọc và thực thi khi tiếp tục|
| **SAIPEN** |Trạng thái thực thi sống, hàng đợi công việc, lịch sử sự kiện, kiến thức bền vững và quy tắc tiếp tục được kiểm tra bởi máy — trong các tệp bình thường bên cạnh mã|Không có gì; sự kết hợp đó là hợp đồng|

Sự khác biệt không phải là bất kỳ tệp nào. Đó là SAIPEN thực hiện bước tiếp tục
có thể kiểm tra bởi máy: hành động đầu tiên của tác nhân lạnh sau`/saipen continue`là
được xác định bởi thông tin đã lưu trữ`next_action`và được xác minh bởi trình xác minh, không
được tái tạo từ trí nhớ.

## Bằng chứng kỹ thuật

SAIPEN kết hợp một giao thức tệp bình thường chuẩn mực với một giao thức có thể thực thi, hướng đến sự thất bại
Kiểm tra. Kho lưu trữ thể hiện thiết kế giao thức/máy trạng thái, Python
công cụ, trạng thái được điều khiển bởi lược đồ, lập luận phục hồi, kiểm thử hồi quy,
ranh giới quy trình đa tác nhân, và kỷ luật quy định.

- **Hợp đồng được thiết kế.** [SPEC.md](SPEC.md)xác định mô hình tiếp tục có tệp đính kèm
mô hình hợp đồng ổn định trên đĩa;[CORE.md](saipen/CORE.md)
và[MAINTENANCE.md](saipen/MAINTENANCE.md)xác định hành vi chuẩn hiện tại.
- **Trạng thái được kiểm tra bởi máy.**The stdlib-only canonical
  [trình kiểm tra](tools/validate.py)đọc trạng thái
  [mô hình STATE](extensions/schemas/state.schema.json)và kiểm tra sự chuyển tiếp giai đoạn
phụ thuộc vé, liên kết đồ thị sự kiện, các bất biến
chéo tài liệu, khả năng và trạng thái phục hồi.
- **Độ phủ lỗi.** [CONFORMANCE.md](saipen/CONFORMANCE.md)ánh xạ
yêu cầu đến[các trường hợp kiểm thử](tests/scenarios/); the
  [chạy kịch bản](tools/run_scenarios.py)thực thi các trường hợp kiểm tra cấu trúc thông qua việc thông qua/thất bại
bao gồm trạng thái phục hồi bị hỏng, chuyển tiếp không hợp lệ, chu kỳ phụ thuộc, và
các hạn chế chỉ đọc.
- **Kiểm soát hồi quy.** [audit_checks.py](tools/audit_checks.py)thay đổi
các bản sao đã biết tốt và chứng minh các kiểm tra của trình xác minh vẫn có thể thất bại, thay vì
coi một kiểm tra luôn xanh là bằng chứng.
- **Lớp có thể thực thi.** [saipen.py](tools/saipen.py)cung cấp trạng thái được ghi nhật ký
các thao tác;[bootstrap/](bootstrap/)giữ nguyên cài đặt, gỡ cài đặt và xuất
các công cụ hỗ trợ, với tùy chọn[cài đặt hook pre-commit](tools/install_hook.py).
- **Các quyết định rõ ràng.**Trạng thái giao thức cốt lõi là các tệp bình thường không có phụ thuộc thời gian chạy
công cụ xác minh tiêu chuẩn và công cụ dòng lệnh yêu cầu Python, nhưng chỉ sử dụng
thư viện tiêu chuẩn và không cần`pip`cài đặt.

## Kiến trúc

Ba lớp, phụ thuộc một chiều nghiêm ngặt:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Lõi không phụ thuộc vào Bảo trì: với việc tắt tiến hóa độc lập, SAIPEN
vẫn là một giao thức tiếp nối đầy đủ — một tác nhân lạnh vẫn có thể tiếp tục.

- **Máy trạng thái lõi** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Bảo trì độc lập**— bảng dừng(không có gì khả thi trong`## TODO`,
không có gì trong`## DOING`)và không`BLOCKED`? Chuyển tiếp tự động`HUNT` (quét lỗi)
  → `ADD` (tiến hóa tính năng) → `HUNT`, không có câu hỏi nào được đặt. Một phiên đang ngồi tại
  `BLOCKED`không tự động săn mồi
  ([Bảo trì § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Chế độ Mục tiêu** — `/saipen goal <objective>`xoay bảng và chạy
mục tiêu tiến lên thông qua VERIFY/REVIEW, rơi vào bảo trì tự động
cho đến khi quy tắc hoàn thành được kích hoạt hoặc lần chạy đạt đến giới hạn của nó(3 làn sóng / 20 vé,
sau đó kiểm tra điểm và báo cáo) ([Bảo trì § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Củng cố**— đầu vào theo lô được phân tích thành các vé một cách tỉ mỉ từng cái một
  (CORE § 1.8); việc tiếp tục cây dữ liệu bẩn bảo tồn công việc chưa được xác nhận(CORE § 1.5);
các giá trị giống bí mật được xóa khỏi nhật ký(`sk-***`) (CORE § 1.2).

## Các lệnh phổ biến

Các điểm nhập thông thường; bề mặt hiện tại đầy đủ nằm trong
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Lệnh|Làm|
|---|---|
| `/saipen set` |Nhận dự án: tạo`.saipen/`trạng thái|
| `/saipen continue` |Khôi phục từ trạng thái dự án đã lưu — không cần hướng dẫn lại|
| `/saipen plan` |Chuyển yêu cầu hoặc danh sách công việc thô thành các phiếu công việc|
| `/saipen goal <text>` |Thực thi sóng tự động theo một mục tiêu mới|
| `/saipen validate` |Chạy các kiểm tra tuân thủ|
| `/saipen status` |Báo cáo chỉ đọc: giai đoạn, phiếu công việc, chướng ngại, độ cũ|
| `/saipen stop` |Điểm kiểm tra và dừng lại|

<details>
<summary><b>More commands</b></summary>

|Lệnh|Thực hiện|
|---|---|
| `/saipen hunt` |Thực hiện kiểm tra lỗi/cải tiến ngay lập tức|
| `/saipen markhunt` |Kiểm toán khô, không giới hạn — ghi lại kết quả, không sửa chữa gì cả|
| `/saipen ship` |Cổng phát hành; xác nhận, gắn nhãn và đẩy lên khi được phép|
| `/saipen clean` |Làm sạch bảng và trạng thái|
| `/saipen translate` |Nhà máy dịch thuật cô lập|
| `/saipen prepare` / `/saipen collect` |Làm việc gói để bàn giao / tích hợp một gói sẵn sàng|
| `/saipen test` |Chạy bộ thử nghiệm đã khai báo, chỉ báo cáo|
| `/saipen crew` |Vòng tuần hoàn phi công theo thứ tự cố định(săn → tái tạo → tiếp nhận → xây dựng → dịch thuật → tài liệu → vận chuyển) |
| `/saipen improve` |Kiểm toán siêu kiểm soát về cải tiến giao thức|
| `/saipen sub ...` |Khởi tạo/thu nhận các đại lý con chỉ đọc|

**Gói các khóa.** `ee`/`qq`chuẩn bị các gói dịch thuật/wiki đầy đủ mà không
tích hợp;`eee`/`qqq`chỉ chấp nhận các gói đã sẵn sàng, sau đó tích hợp, xác minh,
xem xét và đẩy.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)đi qua toàn bộ
nhóm được xây dựng sẵn theo một thứ tự cố định — cảm biến(saihunt, saitest, saipython, saiui),
các nhà sản xuất(saitranslate, saiwiki)và Core là người viết duy nhất trên cây chính —
cho đến khi một lần chạy mới không còn gì thực sự để thay đổi. Nó thêm chính xác một
cơ chế riêng của mình: mục tiêu điều phối bền vững(``execution_intent:
hội tụ` with `converge_target: crew`)đó làm cho mạch có thể tiếp tục và
có thể suy ra từ bằng chứng khi xảy ra sự cố.`saipen crew --dry-run --json`suy ra được
chỉ đọc mạch;`bootstrap/saipen_crew.*`là một trợ lý đa cửa sổ thủ công TÙY CHỌN
không phải là điều`saipen crew`có nghĩa. Xem
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## SAIPEN là gì không phải

- **Một mô hình LLM hoặc một mô hình**— đó là một giao thức các tác nhân tuân theo, không phải là trí tuệ.
- **Một IDE hoặc một cơ sở dữ liệu bộ nhớ được lưu trữ**— trạng thái là các tệp bình thường trong dự án của bạn;
không có gì được lưu trữ.
- **Một sự thay thế cho Git**— Git vẫn sở hữu lịch sử phiên bản; hãy thực hiện commit
  `.saipen/`giống như bất kỳ mã nguồn nào khác.
- **Đồng thuận phân tán**— xem ranh giới đồng thời bên dưới.
- **Một cam kết rằng một LLM sẽ đưa ra các quyết định kỹ thuật đúng đắn**— nó
làm giảm mất ngữ cảnh và sự trôi dạt hành vi; nó không khiến các tác nhân ngẫu nhiên
bất khả chiến bại.

Nhiệm vụ của SAIPEN là một hợp đồng trạng thái/không gian trạng thái tiếp nối cùng với xác minh và công cụ —
trao cho đại lý tiếp theo một điểm bắt đầu được kiểm tra bởi máy, không phải là phép thuật.

**Giới hạn đồng thời.**Các thay đổi trạng thái được ghi nhật ký(SAIOPS)sử dụng một
khóa cấp dự án và một nhật ký phục hồi([OPS § 5](saipen/OPS.md#5-locks)).
Các chỉnh sửa dự án thông thường và các tác giả không kết nối nằm ngoài khóa đó. SAIPEN
không phải là sự đồng thuận phân tán, vì vậy các tác giả không kết nối yêu cầu sự
tùy chỉnh bên ngoài([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Hệ sinh thái

|Dự án|Mối quan hệ với SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Trung tâm điều khiển cục bộ trên Windows cho các dự án SAIPEN — tự phát hiện`.saipen/`các không gian làm việc, trực quan hóa trạng thái sống và kết quả kiểm tra tuân thủ, quản lý vé và khởi chạy các CLI AI. Là một công cụ hỗ trợ, không phải là quyền lực chính.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Phiên bản fork CodeNomad phía downstream tích hợp SAIPEN: chèn`BOOT.md`/`STYLE.md`vào các lần khởi động OpenCode, hiển thị các phím tắt SAIPEN và các chế độ xem trạng thái dự án, và thêm hàng đợi lệnh nhắc bền vững.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Bảng ghi chú và quản lý đoạn mã di động trên Windows tự phát hiện`.saipen/`các thư mục và thêm trình xem STATE/BOARD/LOG chỉ đọc.|

## Tài liệu

|Tài liệu|Là gì|
|---|---|
| [SPEC.md](SPEC.md) |Kiến trúc chính thức, mục tiêu thiết kế, bài kiểm tra litmus|
| [CORE.md](saipen/CORE.md) |Tiếp tục chuẩn mực, máy trạng thái và hợp đồng lệnh|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Bảo trì tự chủ và Chế độ Mục tiêu|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Yêu cầu có thể thực thi/ hành vi và quy tắc kiểm tra tuân thủ|
| [GUIDE.md](GUIDE.md) |Hướng dẫn dành cho người dùng|
| [RFC.md](saipen/RFC.md) |Chuyển hướng tính tương thích đến các tài liệu quy chuẩn được tách riêng|
| [STYLE.md](saipen/STYLE.md) |Phong cách và giọng nói giao tiếp của Agent|
| [UI.md](saipen/UI.md) |Hướng dẫn thiết kế giao diện UI cổ điển kiểu vàng|
|Brochure|Brochure thuyết trình —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Tiếng Anh](guides/GUIDE_EN.md) · 🇪🇪 [Tiếng Estonia](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Tiếng Đức](guides/GUIDE_DE.md) · 🇫🇷 [Tiếng Pháp](guides/GUIDE_FR.md) · 🇪🇸 [Tiếng Tây Ban Nha](guides/GUIDE_ES.md) · 🇮🇹 [Tiếng Ý](guides/GUIDE_IT.md)

🇵🇹 [Tiếng Bồ Đào Nha](guides/GUIDE_PT.md) · 🇳🇱 [Tiếng Hà Lan](guides/GUIDE_NL.md) · 🇵🇱 [Tiếng Ba Lan](guides/GUIDE_PL.md) · 🇸🇪 [Tiếng Thụy Điển](guides/GUIDE_SV.md) · 🇩🇰 [Tiếng Đan Mạch](guides/GUIDE_DA.md)

🇫🇮 [Tiếng Phần Lan](guides/GUIDE_FI.md) · 🇳🇴 [Tiếng Na Uy](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Tiếng Thổ Nhĩ Kỳ](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Tiếng Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Tiếng Séc](guides/GUIDE_CS.md) · 🇷🇴 [Tiếng Romania](guides/GUIDE_RO.md) · 🇭🇺 [Tiếng Hungary](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Tiếng Slovak](guides/GUIDE_SK.md) · 🇭🇷 [Tiếng Croatia](guides/GUIDE_HR.md)

</details>

## Ghi chú cấu hình

**Ngôn ngữ trả lời.**Đại lý trả lời bằng**Tiếng Estonia**mặc định — đó là một
cài đặt, không phải yêu cầu của giao thức, và không có gì khác về SAIPEN là tiếng Estonia.
Giao thức, mã nguồn, các lần commit và mọi tài liệu đều giữ nguyên tiếng Anh ở mọi
giá trị. Thay đổi nó tại một nơi: dòng`reply_language:`ở đầu của
[`saipen/STYLE.md`](saipen/STYLE.md). `et`Tiếng Estonia,`en`Tiếng Anh,`ru`Tiếng Nga,
`auto`chọn từ thông điệp bạn đã gửi.

**Các bộ điều hợp.**Nền tảng không được hỗ trợ bởi trình tiêm(DeepSeek, Qwen, độc lập
OpenAI, v.v.)? Ghi chú theo nền tảng sống trong`extensions/adapters/`.

## Hình ảnh chụp màn hình

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
