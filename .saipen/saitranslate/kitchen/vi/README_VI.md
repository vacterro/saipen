<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Giao thức tiếp tục công việc dành cho các agent lập trình AI.** Bộ nhớ dự án bền vững bằng
markdown thuần túy, nhờ đó một agent mới chưa từng có lịch sử trò chuyện chỉ cần chạy `/saipen continue`
và tiếp tục công việc trong chưa đầy một phút -- không cần giải thích lại, bất kỳ nhà cung cấp nào, bất kỳ ngày nào.

**Một lệnh. Không hề mất trí nhớ.**

**Phím tắt:** `cc` tiếp tục Goal Mode đang chạy, `sss` báo trạng thái mà không đụng vào mã và `ss` lưu điểm kiểm tra rồi dừng. [Xem bản đồ đầy đủ 15 phím](saipen/RFC.md#110-command-surface). Các cặp song sinh Cyrillic cũng hoạt động: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Ngôn ngữ trả lời.** Tác nhân trả lời mặc định **bằng tiếng Estonia** — đó là cài đặt, không phải sự kỳ quặc, và không có gì khác trong SAIPEN là tiếng Estonia. Thay đổi ở một nơi: dòng `reply_language:` ở đầu [`saipen/STYLE.md`](saipen/STYLE.md). `et` tiếng Estonia, `en` tiếng Anh, `ru` tiếng Nga, `auto` chọn theo ngôn ngữ tin nhắn bạn gửi. Giao thức, mã nguồn, commit và mọi tài liệu vẫn bằng tiếng Anh ở mọi giá trị.

**v7.202.0** | [Đặc tả](SPEC.md) | [Hướng dẫn](GUIDE.md) | [RFC](saipen/RFC.md) | [Phong cách](saipen/STYLE.md) | [Giao diện UI](saipen/UI.md) | [Độ tuân thủ](saipen/CONFORMANCE.md) | markdown thuần túy | không phụ thuộc | MIT

```text
Người dùng -> /saipen continue
Agent      -> đọc STATE ("Tôi cần làm gì ngay bây giờ?")
Agent      -> đọc BOARD ("Tôi sẽ tiếp nhận nhiệm vụ nào?")
Agent      -> đọc next_action (thực thi lệnh)
Agent      -> Làm việc.
```

### Trạng thái Dự án > Bộ nhớ Mô hình
Bộ nhớ nằm trong dự án, không phải trong đầu của mô hình. `Dự án -> Bộ nhớ -> LLM` trở thành `Dự án -> Trạng thái SAIPEN -> LLM`.

### Logic & Cam kết Cốt lõi của Giao thức
- **Máy Trạng thái Cốt lõi**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Tự chế độ không cần nhắc**: Không còn việc cần làm? Tự động chuyển đổi `HUNT` (quét lỗi) → `ADD` (phát triển tính năng) → vòng lặp `HUNT`. Không đặt bất kỳ câu hỏi nào.
- **Kích hoạt Trực tiếp**: `/saipen clean` (dọn dẹp repo), `/saipen translate` (nhà máy dịch thuật độc lập `.saipen/saitranslate/`), `/saipen markhunt` (kiểm toán toàn bộ không giới hạn, chỉ ghi lại), `/saipen prepare` (đóng gói công việc để bàn giao), `/saipen validate` (kiểm tra độ tuân thủ), `/saipen goal` (thực thi làn sóng tự chủ). Meta/điều khiển: `/saipen status` (báo cáo chỉ đọc), `/saipen stop` (tạo checkpoint và dừng). Danh sách đầy đủ: RFC.md § 1.10.
- **Độ tin cậy Nghiêm ngặt**: Phân tích cú pháp đầu vào theo đợt (xử lý từng thẻ công việc surgical), tiếp nhận cây làm việc dở dang (không bao giờ xóa công việc chưa commit), ẩn thông tin bí mật (`sk-***`).

## Các Dự án Sử dụng SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Công cụ quản lý prompt hiệu năng cao được tích hợp sẵn giao thức bộ nhớ SAIPEN.

## Hai Lớp

| Lớp | Bắt buộc | Mục đích |
|---|---|---|
| **Cốt lõi (Core)** | ✅ | Tiếp tục công việc an toàn |
| **Bảo trì (Maintenance)** | Trên lớp Cốt lõi | Phát triển phần mềm mà không cần giao việc |

**Phát triển Tự động.** Không còn danh sách việc cần làm, gõ `/saipen`: `HUNT` kiểm toán lỗi, mã thừa, test thất bại. Sạch sẽ? `ADD` xây dựng tính năng thiếu rõ ràng tiếp theo, xác minh, rồi lại kiểm toán. Sản phẩm hoàn thiện -> dừng lại một cách êm đẹp.

**Chế độ GOAL.** `/saipen goal <những gì bạn muốn>` chuyển hướng bảng công việc (thẻ cũ bị hạ cấp, không bao giờ bị xóa) và đẩy mục tiêu mới tiến lên -- không cần "tôi có nên tiếp tục không?" giữa các thẻ, VERIFY/REVIEW không bao giờ bị bỏ qua. SHIP tự động push lên remote hiện có; một repo hoàn toàn mới vẫn sẽ hỏi một lần. Phát hành mục tiêu cũng không phải là điểm dừng -- nó sẽ chuyển thẳng sang chế độ bảo trì tự động HUNT/ADD cho đến khi sản phẩm trưởng thành, bị chặn, hoặc chạy đạt giới hạn (3 làn sóng / 20 thẻ, sau đó tạo checkpoint và báo cáo).

## Bắt đầu Nhanh

**1. Cài đặt một lần trên mỗi máy** -- hướng dẫn Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex va b?t k? trinh d?c ~/.agents/skills chung nao (FreeBuff, v.v.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Bắt đầu một dự án** -- mở agent trong thư mục của bạn, gõ:
> `saipen set`

Chưa cài đặt? Dán một dòng này cho bất kỳ agent nào:
> Đọc <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md và làm theo.

Nền tảng không có trong danh sách trên (DeepSeek, Qwen, OpenAI độc lập, v.v.)?
Ghi chú cho từng nền tảng nằm tại `extensions/adapters/`.

## Liên kết Tài liệu & Đặc tả
- **[SPEC.md](SPEC.md)** -- kiến trúc chính thức, mục tiêu thiết kế, bài kiểm tra nhanh.
- **[RFC.md](saipen/RFC.md)** -- đặc tả quy chuẩn được thực thi bởi agent.
- **[GUIDE.md](GUIDE.md)** -- hướng dẫn cho người dùng & bản tóm tắt dễ hiểu:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- định nghĩa phong cách giao tiếp & giọng văn của agent.
- **[UI.md](saipen/UI.md)** -- hướng dẫn thiết kế giao diện UI Vintage Golden.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- kịch bản kiểm tra hành vi & quy tắc trình xác thực.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## Ảnh chụp màn hình

<details>
<summary>Nhấp để mở rộng</summary>

<img src="assets/screenshot-freebuff.png" alt="Hướng dẫn tác nhân FreeBuff" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set trong nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="Ảnh chụp màn hình saipen 2026-08-01" width="600"/>

</details>

<!-- source-digest: README.md sha256:951d8044313a6456 -->
