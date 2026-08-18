# Thuật ngữ, ký hiệu và công thức của dự án

Tài liệu tra cứu cho hệ BB84 qua kênh quang không dây dưới nước (UWOC) mô phỏng
trên FPGA. Mọi công thức ở đây đều dẫn tới đúng dòng code hiện thực nó, để khi
số liệu không khớp thì biết mở file nào.

---

## 1. Thuật ngữ của quy trình đo

Đây là những chữ xuất hiện trên dòng lệnh và trong bảng kết quả.

### Pha (`--phase`)

| Pha | Công tắc | Nghĩa |
|---|---|---|
| `fixed` | `SW[1] = 0` | Tham số phát cố định: λ do PC đặt, công suất = 8, khe thời gian = TURBO |
| `adaptive` | `SW[1] = 1` | `adaptive_controller.v` tự chọn λ, công suất, khoảng nghỉ, và có quyền **ngắt phát** |

Ở chế độ PC (`SW[9] = 1`) máy tính cấp sẵn cơ sở đo cho cả Alice lẫn Bob, nên
`adapt_basis_prob` bị vô hiệu. Những gì bộ điều khiển thích ứng còn thay đổi
được là `active_lambda`, `active_power`, `eff_gap` và `tx_permitted`
([top_module.v:154-156](verilog/top_module.v#L154-L156),
[:594-601](verilog/top_module.v#L594-L601)).

> ⚠ **Ở chế độ PC, `tx_permitted` KHÔNG có tác dụng** — nó chỉ được kiểm tra ở
> nhánh `!pc_input_mode` ([top_module.v:674](verilog/top_module.v#L674)). Trạng
> thái PAUSE **vẫn phát**, và phát ở cường độ cao nhất (`CON_POWER = MU_CAP = 12`).
> Xem chứng minh đầy đủ ở [§2.7](#27-pha-adaptive--khi-l-và-μ-cũng-có-chỉ-số-thời-gian).
> Vậy `mode = 3` trong log click phải đọc là *"bộ điều khiển tuyên bố PAUSE"*,
> **không phải** *"bộ điều khiển đã ngừng phát"*.

Từ bitstream **[v13]** mỗi dòng click còn mang theo `mode`, `mu`, `lam_idx` **của
chính qubit đó**, nên hành vi bộ điều khiển đọc được trực tiếp từ
`data/clicks_adaptive_*.csv` chứ không phải suy đoán. Số liệu mục A hiện tại
(L3, clear ocean):

| d [m] | μ trung bình (theo click) | tỉ lệ 450 nm | tỉ lệ 650 nm | tỉ lệ PAUSE |
|---:|---:|---:|---:|---:|
| 5 | 9.90 | 73.2 % | 0.0 % | 0.0 % |
| 15 | 10.62 | 84.5 % | 0.0 % | 0.0 % |
| 25 | 11.33 | 75.5 % | 0.0 % | 5.3 % |
| 35 | 11.65 | 100 % | 0.0 % | 30.8 % |
| 45 | 11.97 | 100 % | 0.0 % | 94.4 % |

Ba điều đọc được từ bảng này, và cả ba đều cần nêu trong bài:

1. **450/532 nm trộn nhau ở cự ly ngắn là ĐÚNG**, không phải lỗi — bộ leo đồi cố
   ý thử ứng viên. Dấu hiệu hỏng là **650 nm chiếm tỉ lệ lớn trong nước trong**;
   ở bộ số liệu này nó bằng 0. Đọc dấu hiệu này **theo loại nước**: cũng tỉ lệ
   650 nm ấy lại là đáp án đúng ở harbor (xem bảng mục D ngay dưới).
2. **PAUSE tăng theo cự ly tới 94 %** — nhưng đọc cho đúng: đây là tỉ lệ click
   *đến trong lúc bộ điều khiển ở trạng thái PAUSE*, **không phải** tỉ lệ thời
   gian nó ngừng phát. Ở chế độ PC cờ `tx_permitted` không nối vào đường phát
   ([§2.7](#27-pha-adaptive--khi-l-và-μ-cũng-có-chỉ-số-thời-gian)), nên PAUSE
   hiện chỉ là **cảnh báo được ghi nhận**, chưa phải hành động. Muốn dùng nó làm
   luận điểm bảo mật thì phải sửa RTL rồi đo lại.
3. **μ bị đẩy từ 8 lên ~12** — xem cảnh báo ở [mục 7.3](#73-chỗ-lệch-cần-quyết-định-trước-khi-viết-bài).
   Cột `mu` này lấy điều kiện "đã có click", mà μ cao thì dễ click hơn, nên nó
   **lệch cao hơn** μ trung bình theo lần phát. Đừng trích nó như "cường độ bộ
   điều khiển đã dùng".

Mục D adaptive (đo 2026-08-10…13, L3) là nơi λ mới nói lên điều gì đó, vì ở nước
đục thứ tự $c(\lambda)$ đảo lại:

| Nước | d [m] | 450 nm | 532 nm | 650 nm | μ̄ | PAUSE |
|---|---:|---:|---:|---:|---:|---:|
| coastal | 2 | 47.1 % | 52.9 % | 0.0 % | 9.0 | 0 % |
| coastal | 4 | 38.9 % | 61.1 % | 0.0 % | 9.0 | 0 % |
| coastal | 6 | 31.2 % | 63.9 % | 4.9 % | 9.9 | 0 % |
| coastal | 8 | 19.9 % | 77.8 % | 2.3 % | 10.7 | 0 % |
| coastal | 10 | 98.5 % | 1.3 % | 0.2 % | 11.3 | 10.8 % |
| coastal | 13 | 100 % | 0.0 % | 0.0 % | 11.9 | 30.8 % |
| coastal | 16 | 100 % | 0.0 % | 0.0 % | 11.9 | 93.8 % |
| coastal | 19 | 100 % | 0.0 % | 0.0 % | 11.8 | 93.9 % |
| harbor | 0.5 | 31.7 % | 68.3 % | 0.0 % | 9.8 | 0 % |
| harbor | 1.0 | 16.5 % | 59.1 % | **24.4 %** | 10.4 | 0 % |
| harbor | 1.5 | 24.8 % | 0.0 % | **75.2 %** | 11.3 | 0 % |
| harbor | 2.0 | 100 % | 0.0 % | 0.0 % | 11.9 | 0 % |
| harbor | 2.5 | 100 % | 0.0 % | 0.0 % | 11.9 | 94.9 % |
| harbor | 3.0 | 100 % | 0.0 % | 0.0 % | 9.0 | 92.9 % |
| harbor | 3.5 | 100 % | 0.0 % | 0.0 % | 9.0 | 95.7 % |

Bộ điều khiển chọn 450 nm ở nước trong, 532 nm ở coastal, 532 → 650 nm ở harbor —
đúng thứ tự mà mô hình dự đoán, mà không hề được cho biết loại nước. Đây là khẳng
định adaptive **không** dính confound μ; xem [§2.7](#27-pha-adaptive--khi-l-và-μ-cũng-có-chỉ-số-thời-gian)
cho phần định lượng, kể cả phản ví dụ ở harbor 2 m.

> **Hai đường vào PAUSE, phân biệt được bằng chính cột `mu`.** Nhìn hai dòng cuối:
> PAUSE 93–96 % nhưng μ̄ = **9**, không phải 12. Đó là đường **link chết**
> ([adaptive_controller.v:338-344](verilog/adaptive_controller.v#L338-L344)):
> `stale_windows ≥ DEAD_WINDOWS` đặt `mode <= 2'b11` nhưng **không đụng tới**
> `power_level`, nên μ giữ nguyên giá trị cũ (MOD_POWER = 9 sau reset). Còn PAUSE
> do *quyết định trên một cửa sổ hợp lệ* ([:416-421](verilog/adaptive_controller.v#L416-L421))
> mới đặt `power_level <= CON_POWER = 12`. Số liệu tách bạch: harbor 2.5 m và
> coastal 16/19 m ra `mode3/μ12`, còn harbor 3.0/3.5 m — nơi `P_click` đã rơi
> xuống sát nền $Y_0 = 1.3\times10^{-5}$ — ra `mode3/μ9`. Vậy `mode = 3` một mình
> **không** đủ để nói bộ điều khiển đang làm gì; phải đọc kèm `mu`.

### Mục A/B/C/D (`--sections`)

Ma trận đo chia làm bốn mục, định nghĩa ở `build_matrix()`
([fpga_collect.py:373](python/fpga_collect.py#L373)). Mỗi mục trả lời một câu hỏi
và nuôi một hình trong bài báo.

| Mục | Câu hỏi | Quét cái gì | Cố định cái gì | Ngân sách một điểm |
|---|---|---|---|---|
| **A** | QBER và SKR suy giảm theo cự ly ra sao? | 10 cự ly, 5→50 m | clear ocean, mức nhiễu loạn `--turb`, 450 nm | 150…5000 bit sàng, giảm dần theo cự ly |
| **B** | Nhiễu loạn có làm tăng QBER không? | L1…L5 | clear ocean, **25 m**, 450 nm | **160 × 65 536 lần phát** (không phải bit sàng) |
| **C** | λ tối ưu có phụ thuộc loại nước không? | 450/532/650 nm × {clear ocean, harbor} | L3, cự ly ngắn nhất | 400 bit sàng, trần 12 phút |
| **D** | Ba loại nước khác nhau thế nào? | **quét đủ cự ly**: coastal 2→19 m (8 điểm), harbor 0.5→3.5 m (7 điểm) | L3, 450 nm | như mục A, mỗi loại nước một kế hoạch riêng |

Mục A là hình chủ đạo. Mục D **không** phải ba điểm mẫu mà là hai đường cong đầy
đủ — cần thế mới thấy mỗi loại nước cắt ngưỡng 11 % ở đâu. `RANGE_PLAN`,
`RANGE_PLAN_COASTAL`, `RANGE_PLAN_HARBOR`
([fpga_collect.py:323](python/fpga_collect.py#L323)) là ba bảng chỉnh tay được,
mỗi bảng gói trong ~4.5 giờ.

Câu trả lời cho mục B là **"QBER gộp thì không, QBER theo khối thì có"** — và đó
chính là kết quả đáng đo. Đo được ở 25 m:

| Mức | QBER gộp | QBER trung bình theo khối | std theo khối | outage |
|---|---:|---:|---:|---:|
| L1 | 3.72 % | 3.71 % | 2.84 % | 0.013 |
| L3 | 3.74 % | 3.70 % | 3.48 % | 0.031 |
| L5 | 3.49 % | 13.89 % | 24.53 % | 0.250 |

Hai lý do cột "gộp" phẳng: `P_click` gần tuyến tính theo `h` nên kỳ vọng triệt
tiêu fading, **và** phép gộp đánh trọng số mỗi khối theo chính số click của nó —
khối fade sâu gần như không đóng góp vào con số quyết định độ an toàn của chính
nó. Xem `window_statistics()`
([uwoc_channel_model.py:538](python/uwoc_channel_model.py#L538)) cho phía mô hình
và `python python/sim_table.py --blocks` cho phía đo.

> **Ngân sách của một phép đo ĐỘ TÁN thì tính theo LẦN PHÁT, không theo bit sàng.**
> Dừng khi đủ N bit sàng là quy tắc **tương quan với fading**: điểm nào mở đầu vào
> đoạn sáng thì đạt chỉ tiêu sớm rồi dừng ngay ở đó, mẫu bị thiên về khối `h` cao
> và độ tán bị **hạ thấp**. Lần chạy mục B đầu tiên đúng như vậy: L5 đạt 6000 bit
> sàng trong 129 khối trong khi L1 cần 154 — mức nhiễu loạn mạnh nhất lại có mẫu
> nhỏ nhất và đẹp nhất, ngược hoàn toàn. Nay mục B dùng `target_qubit`
> ([fpga_collect.py:148](python/fpga_collect.py#L148)).

### `chunk`

Số lệnh qubit gửi liên tiếp qua UART trước khi dừng lại đọc kết quả.

Không phải "kích thước lô dữ liệu" — nó là độ sâu ống dẫn. Dưới nước hơn 99%
qubit không click, nên nếu đọc kiểu chờ-từng-qubit thì mỗi qubit đều phải chờ
hết timeout của cổng COM và tốc độ đo bị ghim ở `1/timeout` bất kể FPGA nhanh cỡ
nào. Gửi theo chunk rồi hút cả buffer một lần
(`_harvest()`, [fpga_collect.py:130](python/fpga_collect.py#L130)) cắt được ràng
buộc đó: giới hạn chuyển về chính tốc độ của FPGA.

Kẹp trần ở **32** vì FIFO lệnh trong `top_module.v` sâu 64 mức
(`CMD_DEPTH`, [:191](verilog/top_module.v#L191)); gửi 64 lệnh một lúc vào FIFO 64
mức thì tràn ngay lần hàng đợi dồn đầu tiên. Script tự kẹp về 32 dù truyền vào
lớn hơn. Kiểm tra trước khi chạy dài: `--chunk-check` đo `P_click` ở chunk = 1 và
ở chunk đang chọn rồi thoát.

Ba tham số điều khiển nhịp gửi:

| Tham số | Mặc định | Nghĩa |
|---|---|---|
| `--qubit-us` | 220 | thời gian FPGA xử lý một qubit **không** click: TX 50 + rx_timeout 160 + gap 10 µs |
| `--report-us` | 4400 | thời gian tốn **thêm** cho một qubit **có** click (dòng báo cáo 42 byte @115 200 mất 3.65 ms) |
| `PACE_MARGIN` | 1.15 | biên an toàn; gửi đúng bằng tốc độ tiêu thụ thì hàng đợi ở tải tới hạn và trôi vào tràn |

Chu kỳ gửi một chunk = `PACE_MARGIN × chunk × (qubit_us + P̂_click × report_us)`,
với `P̂_click = (n_click + 1)/(n + 2)` — làm trơn Laplace, khởi đầu từ 1/2 rồi tự
nới ra khi có số liệu.

### `target_sift` và `cap`

Mỗi điểm đo dừng khi **đủ mẫu** hoặc **hết giờ**, cái nào tới trước.

- `target_sift` — số bit sàng cần đạt. Đây mới là thứ quyết định độ chính xác của
  QBER, không phải số qubit. `RANGE_PLAN`
  ([fpga_collect.py:323](python/fpga_collect.py#L323)) là bảng chỉnh tay được.
- `target_qubit` — số **lần phát** cần đạt, dùng thay cho `target_sift` khi đại
  lượng cần đo là một **độ tán** (mục B). Bằng 0 nghĩa là "tính ngân sách theo
  bit sàng".
- `cap` — trần thời gian, đặt ở khoảng 2× thời gian kỳ vọng. Là lưới an toàn để
  một điểm hỏng không nuốt cả phiên, không phải lịch chạy.

`--scale` chia mục tiêu và nhân trần (dùng để chạy thử). `--cap-scale` **chỉ**
nhân trần, giữ nguyên mục tiêu (dùng khi board chạy chậm hơn dự kiến).

### `tag`

Khóa checkpoint, dạng `{pha}_{mục}_{tên điểm}`, ví dụ `fixed_A_dist_d4_L1`. Mỗi
điểm xong ghi ngay một dòng vào `data/fpga_points.csv`; chạy lại thì tag đã có
sẽ bị bỏ qua.

Tag phải chứa **mọi thứ phân biệt hai lần đo**, nếu không lần sau sẽ bị checkpoint
nuốt mất. Cụ thể:

- **pha** — nên `fixed` và `adaptive` sống chung một file mà không đụng nhau.
- **mức nhiễu loạn** ở mục A (hậu tố `_L1`, `_L2`…) — vì mục A quét cự ly ở *một*
  mức nhiễu loạn do `--turb` chọn. Không có hậu tố này thì chạy `--turb 2` sinh
  ra tag giống hệt `--turb 1`, checkpoint bỏ qua sạch và **phiên đo không thu
  được gì** mà cũng không báo lỗi. Mục B không cần vì tên điểm đã là `B_turb_L3`;
  mục C và D cố định ở L3 nên không đụng.

Hậu tố `_L<n>` đặt ở **cuối** để tag vẫn bắt đầu bằng `A_dist` — đó là tiền tố mà
`paper_figs_uwoc.py` dùng để lọc.

Cái **không** nằm trong tag: loại nước và bước sóng ở mục A (luôn là clear ocean
450 nm). Muốn quét mục A ở loại nước khác thì phải thêm vào tag trước, hoặc dùng
`--out` để ghi sang thư mục riêng.

---

## 2. Mô hình kênh

Toàn bộ nằm trong [uwoc_channel_model.py](python/uwoc_channel_model.py). Các
phương trình được đánh số (1)…(32) để trích thẳng vào bài báo.

### 2.0 Ký hiệu và quy ước

**Quy ước quan trọng nhất — phân biệt `h` và `h_f`.** Hai chữ này rất dễ lẫn và
lẫn là sai một bậc suy hao:

| Ký hiệu | Là gì | Có chứa L không |
|---|---|---|
| $h$ | **hệ số kênh tổng hợp** = suy hao tất định × fading | **CÓ** |
| $h_f$ | **phần fading thuần** = $h_s \cdot h_o$, kỳ vọng đơn vị | **KHÔNG** |

Hàm `n_bar()` trong code nhận **$h_f$**, không nhận $h$ — xem
[uwoc_channel_model.py:616](python/uwoc_channel_model.py#L616):
`n_bar(h_s * h_o, ...)`. Viết $\bar n = \mu\,h_\ell\,h\,\eta_{det}$ với $h$ là hệ số tổng
hợp là **nhân L hai lần**; ở 15 m clear ocean 450 nm sai số là 5.1 lần, và tỉ số
này còn phình theo cự ly vì L vào bình phương.

**Quy ước ngoặc — vuông hay tròn, và vì sao $d$ biến mất khỏi $h_f$.**

| Viết | Nghĩa | Ví dụ |
|---|---|---|
| $f(\cdot)$ ngoặc **tròn** | hàm **tất định**, đối số quyết định giá trị | $h_\ell(d,\lambda;w)$ |
| $x[k]$ ngoặc **vuông** | **dãy rời rạc** theo chỉ số nguyên | $h_f[k]$, $\bar n[k]$ |
| $f(\cdot\,;\theta)$ sau **dấu chấm phẩy** | **tham số của phân bố**, không phải đối số | xem dưới |

$h_f$ **không** phải hàm của $d$ — nó là biến ngẫu nhiên. Cái mà $d$ làm là chọn
xem rút từ phân bố nào:

$$h_s[k] \sim \text{Gamma}\Big(\tfrac{1}{\sigma_s^2(d)},\ \sigma_s^2(d)\Big), \qquad h_o[k] \sim \text{LN/Weibull}\big(\sigma_{ho}^2(d,\lambda,\text{turb})\big)$$

Vậy nên **đừng viết $h_f(d,k)$**: ký hiệu đó ngụ ý biết $h_f$ ở 15 m thì suy ra
được gì đó về $h_f$ ở 25 m trong cùng khối $k$, trong khi thực tế đó là hai lần
rút độc lập từ hai phân bố khác nhau. Muốn nêu rõ phụ thuộc cự ly thì viết

$$h_f[k] \ \sim\ f_{h_f}\big(\,\cdot\ ;\ \sigma_s^2(d),\ \sigma_{ho}^2(d,\lambda,\text{turb})\big)$$

Ngoặc vuông còn mang thêm một thông tin: nó báo ngay rằng quá trình là **rời rạc
theo khối**, khớp với §2.0.1. Viết $h(d,t)$ với $t$ liên tục là gợi một quá trình
có cấu trúc tương quan thời gian mà mô hình này không hề có.

**Bảng ký hiệu đầy đủ:**

| Ký hiệu | Nghĩa | Đơn vị | Giá trị / nguồn | Code |
|---|---|---|---|---|
| $a(\lambda)$ | hệ số hấp thụ | m⁻¹ | Bảng [2] I | `WATER_TYPES` |
| $b(\lambda)$ | hệ số tán xạ | m⁻¹ | Bảng [2] I | `scattering_coef()` |
| $c(\lambda)$ | hệ số suy giảm $=a+b$ | m⁻¹ | | `extinction()` [:403](python/uwoc_channel_model.py#L403) |
| $d$ | cự ly liên kết | m | | |
| $w$ | **loại nước** — nhãn phân loại, KHÔNG phải biến liên tục | — | clear ocean / coastal / harbor | `WATER_TYPES` |
| $h_\ell$ | truyền qua tất định (transmittance $\le 1$, **không** phải "loss") | — | biến $(d,\lambda)$, tham số $w$ | `h_ell()` [:417](python/uwoc_channel_model.py#L417) |
| $h_s$ | fading do **tán xạ** | — | Gamma, $\mathbb{E}=1$ | `sample_h_s()` [:380](python/uwoc_channel_model.py#L380) |
| $h_o$ | fading do **nhiễu loạn** | — | LN/Weibull, $\mathbb{E}=1$ | `sample_h_o()` [:387](python/uwoc_channel_model.py#L387) |
| $h_f$ | fading tổng $=h_s h_o$ | — | $\mathbb{E}=1$ | — |
| $h$ | kênh tổng hợp $=h_\ell\,h_f$ | — | $\mathbb{E}[h]=h_\ell$ | — |
| $\sigma_s^2$ | chỉ số nhấp nháy tán xạ | — | khớp Bảng [2] IV | `sigma2_s()` [:369](python/uwoc_channel_model.py#L369) |
| $\sigma_{ho}^2$ | chỉ số nhấp nháy nhiễu loạn | — | tích phân Nikishov | `sigma2_ho()` [:229](python/uwoc_channel_model.py#L229) |
| $\mu$ | số photon TB mỗi xung phát | photon | 0.1 (danh định) | `LinkConfig.mu` |
| $\eta_{det}$ | hiệu suất tách sóng | — | 0.18, **hằng số** | `LinkConfig.eta_det` |
| $\bar n$ | số **quang điện tử** TB mỗi xung | — | | `n_bar()` [:457](python/uwoc_channel_model.py#L457) |
| $Y_0$ | xác suất click nền mỗi cổng | — | $1.3\times10^{-5}$ | `LinkConfig.Y0` |
| $e_0$ | sai số quang nội tại | — | 0.01 | |
| $k_s$ | hệ số méo phân cực | — | 0.04, **tham số hiệu chỉnh** | `e_pol()` [:441](python/uwoc_channel_model.py#L441) |
| $f_{rep}$ | tần số lặp xung | Hz | 10⁷ | |
| $\tau_{coh}$ | thời gian kết hợp fading | s | 5 ms | |
| $N_{coh}$ | số xung/khối kết hợp | xung | $\tau_{coh}f_{rep}=50\,000$ | `coherence_pulses` |
| $k$ | **chỉ số khối kết hợp** | — | xem §2.0.1 | |
| $m$ | mức cường độ nguyên | — | 8 = danh định, trần 12 | `mu_level` |
| $g$ | cờ cho phép phát | {0,1} | xem §2.7 | `tx_permitted` |

> **`n̄` là số quang điện tử, không phải số photon tới máy thu.** Vì $\eta_{det}$
> đã nằm trong (13). Số photon *đến* máy thu là $\mu\,h_\ell\,h_f$. Viết sai chỗ này là
> lỗi phản biện hay bắt nhất trong các bài QKD.

#### 2.0.1 Chỉ số thời gian $k$ — fading là quá trình **hằng từng khúc**

`h` **không** biến thiên liên tục theo thời gian. Nó bị **đóng băng** trong trọn
một khối kết hợp rồi rút lại độc lập ở biên khối
([uwoc_channel.v:325-328](verilog/uwoc_channel.v#L325-L328)). Vậy nên mọi công
thức phụ thuộc thời gian đều đánh chỉ số bằng **số nguyên $k$**:

$$k = \left\lfloor \frac{\texttt{attempt}}{2^{\,\texttt{coh\_sel}+5}} \right\rfloor \tag{0}$$

Ba điều phải nhớ về $k$:

1. **Đơn vị của $k$ là LẦN PHÁT, không phải giây.** Đại lượng vật lý bất biến là
   tỉ số không thứ nguyên $N_{coh}=\tau_{coh}f_{rep}=50\,000$ xung/khối. Trên
   board `coh_sel = 11` cho 65 536 lần phát/khối. Ở tốc độ đo ~3572 qubit/s, một
   khối chiếm **18.4 giây đồng hồ tường** nhưng biểu diễn **6.55 ms** thời gian
   vật lý — lệch ~2800 lần. Đừng đọc trục thời gian của phiên đo như thời gian thật.
2. **$k$ trùng chỉ số cửa sổ giám sát.** `channel_monitor` đóng cửa sổ mỗi
   $2^{16}=65\,536$ lần phát, đúng bằng một khối fading ở `coh_sel = 11`. Nên
   **một quyết định điều khiển ứng với đúng một mẫu fading** — căn chỉnh cố ý,
   không phải trùng hợp.
3. **Các khối là i.i.d. — không có tương quan thời gian.**

$$h_f[k] \ \perp\ h_f[j] \quad \forall\, j \neq k \tag{0b}$$

   Emulator rút $h_s,h_o$ độc lập ở mỗi biên khối; không có mô hình PSD, AR hay
   Markov nào. **Hệ quả cho pha adaptive: bộ điều khiển về nguyên tắc không thể
   dự đoán fade kế tiếp.** Nó chỉ ước lượng được tính chất *dừng* của liên kết.
   Đây là ràng buộc thiết kế cần khai báo trong bài, không phải khuyết điểm giấu đi.

### 2.1 Hệ số suy giảm

$$c(\lambda) = a(\lambda) + b(\lambda) \tag{1}$$

`a` là hấp thụ, `b` là tán xạ, đơn vị m⁻¹. Bảng tham chiếu ở 532 nm:

| Loại nước | a | b | c | Lưới cự ly |
|---|---|---|---|---|
| Clear ocean | 0.114 | 0.037 | 0.151 | 5…80 m, bước 5 |
| Coastal | 0.179 | 0.219 | 0.398 | 2…43 m |
| Harbor | 0.366 | 1.824 | 2.190 | 0.5…10 m |

Đổi bước sóng thì nhân với `C_LAMBDA_SCALE`. Với clear ocean: 450 nm ×0.85,
532 nm ×1.00, 650 nm ×2.60 — nước trong ưu ái lam-lục. Harbor ngược lại:
450 nm ×1.35, 650 nm ×0.90.

> Các hệ số tỉ lệ theo λ là **giá trị định tính**, không phải phổ đo được. Chúng
> tồn tại để tái tạo kết luận "nước trong ưu lam-lục, nước đục dịch về đỏ".
> Cần số chính xác thì phải thay bằng phổ `a(λ), b(λ)` đo thật.

### 2.2 Suy hao tất định

$$h_\ell(d,\lambda;w) = \underbrace{\min\!\left(1,\ \frac{D_{rx}^2}{\pi\,(d\tan\theta_{div})^2}\right)}_{\text{hình học}} \cdot \underbrace{\exp\!\big(-F\,c(\lambda)\,d\big)}_{\text{Beer–Lambert}} \tag{2}$$

Đọc từng thừa số:

- **Hình học** — chùm phát loe ra hình nón nửa góc $\theta_{div}$, tới cự ly $d$
  thì trải trên diện tích $\pi(d\tan\theta_{div})^2$; khẩu độ thu hứng được phần
  $D_{rx}^2$ trong đó. Kẹp ở $\le 1$ vì **không thu được nhiều hơn lượng phát ra**
  — ở cự ly rất gần thì công thức thô cho giá trị > 1, vô nghĩa vật lý.
- **Beer–Lambert** — suy giảm theo hàm mũ do hấp thụ + tán xạ. $F \le 1$ là hệ số
  hiệu chỉnh cho các photon **bị tán xạ nhưng vẫn rơi vào khẩu độ thu**; không có
  nó thì mô hình phạt quá nặng vì coi mọi photon tán xạ là mất.

$h_\ell$ là **tất định**: cùng $(d,\lambda)$ với tham số $w$ thì luôn ra cùng một số. Mọi
tính ngẫu nhiên của kênh nằm ở $h_f$.

### 2.3 Fading tổng hợp

$$\boxed{\ h[k] \;=\; h_\ell(d,\lambda;w) \cdot h_f[k], \qquad h_f[k] = h_s[k]\cdot h_o[k]\ } \tag{3}$$

$$\mathbb{E}[h_s] = \mathbb{E}[h_o] = \mathbb{E}[h_f] = 1 \quad\Longrightarrow\quad \mathbb{E}[h] = L \tag{4}$$

Đây là điểm khác căn bản so với mô hình khí quyển Gamma–Gamma cũ: dưới nước có
**hai** nguồn fading độc lập, và (4) là lý do chuẩn hóa chúng về kỳ vọng đơn vị —
**toàn bộ suy hao tất định nằm gọn trong $h_\ell$**, hai số hạng ngẫu nhiên chỉ *phân
phối lại* nó theo thời gian chứ không thêm bớt tổng.

#### 2.3.1 $h_s$ — fading do tán xạ (không tồn tại trong khí quyển)

$$h_s \sim \text{Gamma}\big(\alpha = 1/\sigma_s^2,\ \theta = \sigma_s^2\big), \qquad f(h_s) = \frac{h_s^{\alpha-1}e^{-h_s/\theta}}{\Gamma(\alpha)\,\theta^{\alpha}} \tag{5}$$

Kiểm tra chuẩn hóa — đây là chỗ nên tự làm lại bằng tay một lần:

$$\mathbb{E}[h_s] = \alpha\theta = \tfrac{1}{\sigma_s^2}\cdot\sigma_s^2 = 1, \qquad \mathrm{Var}[h_s] = \alpha\theta^2 = \sigma_s^2$$

Nghĩa là **tham số hóa này làm $\sigma_s^2$ trở thành đúng chỉ số nhấp nháy**
$\mathrm{Var}/\mathbb{E}^2$. Cường độ tăng theo cự ly:

$$\sigma_s^2(d) = \exp\big(B\,(d - d_1)\big) \tag{6}$$

với $(B, d_1)$ khớp tuyến tính $\ln\sigma_s^2$ theo $d$ từ Bảng IV của [2];
$d_1$ chính là cự ly mà $\sigma_s^2 = 1$. Riêng harbor là **ngoại suy** theo luật
lũy thừa của $c(\lambda)$, không phải số liệu đo
([:345-363](python/uwoc_channel_model.py#L345-L363)).

#### 2.3.2 $h_o$ — fading do nhiễu loạn đại dương

> ⚠ **Rẽ nhánh theo GIÁ TRỊ $\sigma_{ho}^2$, không theo mức L1…L5.**

$$h_o \sim \begin{cases} \text{Lognormal} & \sigma_{ho}^2 < 1 \quad(\text{nhiễu động yếu})\\[2pt] \text{Weibull} & \sigma_{ho}^2 \ge 1 \quad(\text{trung bình–mạnh})\end{cases} \tag{7}$$

Nói "Lognormal cho L1–L3, Weibull cho L4–L5" là **sai** — chỉ đúng tại cự ly tham
chiếu 20 m. Vì $\sigma_{ho}^2$ tăng theo $d$ (§2.4), cùng một mức nhiễu loạn có
thể đổi nhánh dọc theo lưới cự ly:

| | 5 m | 15 m | 20 m | 25 m | 35 m | 45 m | 50 m |
|---|---:|---:|---:|---:|---:|---:|---:|
| **L3** | 0.015 LN | 0.166 LN | 0.300 LN | 0.470 LN | 0.909 LN | **1.471 W** | **1.795 W** |
| **L4** | 0.056 LN | 0.563 LN | **1.001 W** | **1.548 W** | **2.951 W** | **4.732 W** | **5.000 W** |
| **L5** | 0.210 LN | **1.747 W** | **3.000 W** | **4.538 W** | **5.000 W** | **5.000 W** | **5.000 W** |

**Nhánh Lognormal.** Đặt $h_o = e^{2X}$ với $X\sim\mathcal{N}(\mu_X,\sigma_X^2)$
(quy ước *log-biên độ* của [3], nên có hệ số 2 ở số mũ):

$$\sigma_X^2 = \tfrac14\ln\!\big(1+\sigma_{ho}^2\big), \qquad \mu_X = -\sigma_X^2 \tag{8}$$

Vì sao đúng — dùng $\mathbb{E}[e^{tX}] = e^{t\mu_X + t^2\sigma_X^2/2}$:

$$\mathbb{E}[h_o] = e^{2\mu_X + 2\sigma_X^2} = e^{-2\sigma_X^2+2\sigma_X^2} = 1 \ \checkmark$$
$$\mathbb{E}[h_o^2] = e^{4\mu_X + 8\sigma_X^2} = e^{4\sigma_X^2} = 1+\sigma_{ho}^2 \ \Longrightarrow\ \mathrm{Var}[h_o] = \sigma_{ho}^2 \ \checkmark$$

**Nhánh Weibull.** $h_o = \beta_2 W$ với $W\sim\text{Weibull}(\beta_1)$, dùng
$\mathbb{E}[W^n] = \Gamma(1+n/\beta_1)$:

$$\sigma_{ho}^2 = \frac{\Gamma(1+2/\beta_1)}{\Gamma^2(1+1/\beta_1)} - 1 \quad\text{(giải số cho }\beta_1\text{)}, \qquad \beta_2 = \frac{1}{\Gamma(1+1/\beta_1)} \tag{9}$$

Phương trình đầu **giảm đơn điệu** theo $\beta_1$ nên nghiệm là duy nhất; code
giải bằng `brentq` trên $[0.12,\ 200]$ ([:318-333](python/uwoc_channel_model.py#L318-L333)).
$\beta_2$ chỉ để kéo kỳ vọng về 1.

#### 2.3.3 Phương sai của fading tổng

Hai thừa số **độc lập** và cùng kỳ vọng 1, nên:

$$\sigma_h^2 \equiv \mathrm{Var}[h_f] = \big(1+\sigma_s^2\big)\big(1+\sigma_{ho}^2\big) - 1 \tag{10}$$

Chứng minh một dòng: $\mathbb{E}[h_f^2] = \mathbb{E}[h_s^2]\mathbb{E}[h_o^2] =
(1+\sigma_s^2)(1+\sigma_{ho}^2)$, rồi trừ $\mathbb{E}[h_f]^2 = 1$.

Đây **không** phải tổng hai phương sai — có số hạng chéo $\sigma_s^2\sigma_{ho}^2$.
Ở L5 cự ly xa số hạng chéo này chi phối. → `sigma2_h()`
[sim_table.py:114](python/sim_table.py#L114). Công thức (10) là đầu vào của phép
kiểm phương sai (31).

### 2.4 Chỉ số nhấp nháy do nhiễu loạn

$$\sigma_{ho}^2 = 8\pi^2 k_\lambda^2\, d \int_0^1\!\!\int_0^\infty \kappa\,\Phi_n(\kappa)\left[1 - \cos\!\left(\frac{d\,\kappa^2\,\xi\,\big(1-(1-\Theta)\xi\big)}{k_\lambda}\right)\right]d\kappa\,d\xi \tag{11}$$

với $k_\lambda = 2\pi/\lambda$ là **số sóng** (viết là $k_\lambda$ chứ không phải
$k$, để khỏi lẫn với chỉ số khối $k$ của (0)), $\kappa$ là tần số không gian
[rad/m], $\xi$ là biến đường truyền chuẩn hóa $\in[0,1]$, và $\Theta = 1$ (sóng
phẳng) hoặc $0$ (sóng cầu). Không có dạng đóng — tính số, kết quả nạp vào ROM của
FPGA. → `sigma2_ho()` [:229](python/uwoc_channel_model.py#L229)

Phổ Nikishov của chiết suất nước biển:

$$\Phi_n(\kappa) = 0.388\!\times\!10^{-8}\,\varepsilon^{-1/3}\kappa^{-11/3}\big[1+2.35(\kappa\eta)^{2/3}\big]\frac{\chi_T}{w^2}\Big(w^2 e^{-A_T\delta} + e^{-A_S\delta} - 2w\,e^{-A_{TS}\delta}\Big) \tag{12}$$

$$\delta = 8.284(\kappa\eta)^{4/3} + 12.978(\kappa\eta)^2 \tag{13}$$

| Ký hiệu | Nghĩa | Đơn vị |
|---|---|---|
| $\varepsilon$ | tốc độ tiêu tán động năng rối | m²/s³ |
| $\chi_T$ | tốc độ tiêu tán phương sai nhiệt độ | K²/s |
| $w$ | tỉ lệ cân bằng nhiệt độ / độ mặn, ∈ [−5, 0) | — |
| $\eta$ | vi thang Kolmogorov, 10⁻³ | m |

Trực giác về dấu: **ε nhỏ ⇒ nhiễu loạn mạnh**; **χ_T lớn ⇒ nhiễu loạn mạnh**;
**w → 0 ⇒ độ mặn chi phối, xấu nhất**. Lý do của điều cuối nằm trong công thức:
`A_S` nhỏ hơn `A_T` khoảng 100 lần nên số hạng độ mặn tắt chậm hơn hẳn, để lại
một đuôi phổ dài ở κ lớn.

**Năm mức nhiễu loạn.** Với mỗi mức, `(ε, w)` rải đều trên dải vật lý rồi giải
tuyến tính `χ_T` (vì $\sigma_{ho}^2 \propto \chi_T$) sao cho σ²_ho tại cự ly
tham chiếu 20 m, λ = 450 nm rơi đúng vào:

| Mức | Tên | ε | χ_T | w | σ²_ho @20 m |
|---|---|---|---|---|---|
| L1 | VERYWEAK | 1e-2 | 2.21e-07 | −5.0 | 0.02 |
| L2 | WEAK | 1e-3 | 3.65e-07 | −4.0 | 0.08 |
| L3 | MODERATE | 1e-4 | 5.29e-07 | −3.0 | 0.30 |
| L4 | STRONG | 1e-5 | 5.91e-07 | −2.0 | 1.00 |
| L5 | SEVERE | 1e-6 | 3.85e-07 | −1.0 | 3.00 |

Mốc 1.00 của L4 chính là ranh giới nhiễu loạn yếu/mạnh.

> **Kẹp trần `SIGMA2_HO_MAX = 5.0`.** Công thức trên là kết quả **nhiễu động yếu**
> (lý thuyết Rytov), chỉ đúng khi σ² ≲ 1. Ở cự ly xa và nhiễu loạn mạnh, tích phân
> cho ra σ² ≫ 1 (đo được tới 10⁴ ở 70 m). Đó là dấu hiệu **ra khỏi miền hợp lệ**
> chứ không phải vật lý thật — thực tế σ²_I bão hòa quanh 1–2. Kẹp ở 5.0 và cảnh báo.

### 2.5 Tầng tách photon

Đây là phần khí quyển không có, và là nơi QBER thực sự sinh ra.

**Số quang điện tử trung bình mỗi xung** — chú ý đối số là $h_f$ (fading thuần),
$h_\ell$ chỉ xuất hiện **một lần**:

$$\boxed{\ \bar n[k] \;=\; \mu \cdot h_\ell(d,\lambda;w) \cdot h_f[k] \cdot \eta_{det}\ } \tag{14}$$

$$Y_0 = \big(f_{dark} + f_{bg}\big)\cdot t_{gate} \tag{15}$$

**Xác suất click.** Nguồn kết hợp yếu phát Poisson, nên xác suất có **ít nhất một**
photon tín hiệu được tách là $1 - e^{-\bar n}$. Click nền xảy ra độc lập với xác
suất $Y_0$. Click xảy ra khi **một trong hai** xảy ra:

$$P_{click} = 1 - \underbrace{(1-Y_0)}_{\text{không có click nền}}\underbrace{e^{-\bar n}}_{\text{không có click tín hiệu}} \tag{16}$$

Cấu trúc "HOẶC" này chính là thứ RTL hiện thực (`click = sig_det | noise_det`),
nên (16) không phải xấp xỉ — nó là mô tả chính xác của phần cứng.

**Sai số phân cực do tán xạ nhiều lần** — cơ chế đặc thù dưới nước:

$$e_{pol}(d,\lambda) = \min\!\Big(0.5,\ e_0 + k_s\big(1 - e^{-b(\lambda)\,d}\big)\Big) \tag{17}$$

Với $b\,d$ nhỏ thì $1 - e^{-bd}\approx b\,d$, tức **tuyến tính theo cự ly**, khớp
dạng thực nghiệm trong [1] Fig. 19. Kẹp ở 0.5 = mất sạch thông tin phân cực.
Lưu ý $e_{pol}$ phụ thuộc $\lambda$ qua $b(\lambda)$ — **đổi λ là dịch cả sàn lỗi,
không chỉ tỉ lệ click.**

**QBER:**

$$\boxed{\ \text{QBER} = \frac{e_{pol}\big(1 - e^{-\bar n}\big) + \tfrac12 Y_0}{P_{click}}\ } \tag{18}$$

Cách đọc: tử số đếm **xác suất một click bị sai**. Một click **tín hiệu** sai với
xác suất $e_{pol}$; một click **nền** (đếm tối hoặc ánh sáng môi trường) hoàn
toàn ngẫu nhiên nên sai 50%. Chia cho $P_{click}$ để quy về "sai trên mỗi click".
Ở cự ly xa $\bar n \to 0$, số hạng $\tfrac12 Y_0$ chi phối và QBER $\to 1/2$ —
đúng như trực giác: chỉ còn nhiễu thì bit hoàn toàn ngẫu nhiên.

#### 2.5.1 Vì sao trung bình dài hạn gần như MÙ với nhiễu loạn

Đây là kết quả lý thuyết chống lưng cho mục B, và nên đưa vào bài báo.

Khai triển (16) quanh $\bar n = 0$ với $\bar n_0 \equiv \mu\,h_\ell\,\eta_{det}$ (tức
$\bar n = \bar n_0 h_f$), rồi lấy kỳ vọng theo $h_f$:

$$\mathbb{E}\big[P_{click}\big] = Y_0 + (1-Y_0)\left[\bar n_0 - \frac{\bar n_0^2\,\mathbb{E}[h_f^2]}{2} + \dots\right] = Y_0 + (1-Y_0)\,\bar n_0\left[1 - \frac{\bar n_0\big(1+\sigma_h^2\big)}{2} + \dots\right] \tag{19}$$

Fading chỉ vào từ số hạng bậc hai, qua thừa số $\bar n_0\sigma_h^2/2$. Dưới nước
$\bar n_0 \sim 10^{-3}$, nên **ngay ở L5 với $\sigma_h^2 \approx 4.5$, hiệu chỉnh
tương đối chỉ cỡ $2\times10^{-3}$** — không đo được.

> **Kết luận phải nêu trong bài:** $P_{click}$ gần như **tuyến tính** theo $h_f$
> trong chế độ suy hao lớn, mà kỳ vọng của một hàm tuyến tính thì triệt tiêu
> fading vì $\mathbb{E}[h_f]=1$. Vậy **nhiễu loạn KHÔNG hiện ra ở trung bình dài
> hạn** — nó chỉ hiện ra ở **phương sai giữa các khối** và ở **outage**. Đó chính
> là tín hiệu mà `channel_monitor` và bộ điều khiển thích ứng khai thác, và là lý
> do một phép đo trung bình đơn thuần sẽ kết luận sai rằng "nhiễu loạn không ảnh
> hưởng gì".

`e_pol` mô hình hóa **méo phân cực do tán xạ nhiều lần** — cơ chế đặc thù dưới
nước. Với `b·d` nhỏ thì `1 − e^{−bd} ≈ b·d`, tức tuyến tính theo cự ly, khớp với
dạng thực nghiệm trong [1] Fig. 19. `k_s` là **tham số hiệu chỉnh**, phải khớp
lại theo số liệu đo của từng hệ.

Tham số mặc định (`LinkConfig`, [:155](python/uwoc_channel_model.py#L155)):

| Ký hiệu | Biến | Giá trị | Ghi chú |
|---|---|---|---|
| μ | `mu` | 0.1 photon/xung | nguồn kết hợp yếu |
| η_det | `eta_det` | 0.18 | hiệu suất SPD |
| f_dark | `dark_hz` | 60 Hz | |
| f_bg | `bg_hz` | 200 Hz | ánh sáng môi trường |
| t_gate | `gate_ns` | 50 ns | ⇒ **Y₀ = 1.3×10⁻⁵** |
| f_rep | `f_rep` | 10 MHz | |
| D_rx | `D_rx` | 0.0508 m | khẩu độ thu 2 inch |
| θ_div | `theta_div` | 1 mrad | phần lớn là dự phòng sai lệch ngắm |
| F | `F` | 0.85 | |
| e₀ | `e0` | 0.01 | sai số quang nội tại |
| k_s | `k_s` | 0.04 | **tham số hiệu chỉnh** |
| τ_coh | `tau_coh_ms` | 5 ms | ⇒ 50 000 xung/khối kết hợp |

τ_coh đáng chú ý: nhiễu loạn đại dương biến thiên ở thang mili giây, chậm hơn
chu kỳ qubit khoảng 10⁴ lần, nên `h` coi như **đóng băng** suốt hàng chục nghìn
xung liên tiếp. Đó là lý do fading phải được phân tích theo cửa sổ trượt chứ
không phải theo từng xung.

### 2.6 Tốc độ khóa bí mật

$$H_2(x) = -x\log_2 x - (1-x)\log_2(1-x) \tag{20}$$

$$R = q \cdot f_{rep} \cdot P_{click} \cdot \max\big(0,\ 1 - 2H_2(\text{QBER})\big) \tag{21}$$

Đọc (21) theo bốn thừa số, mỗi thừa số là một tầng "sàng" bớt bit:

| Thừa số | Nghĩa |
|---|---|
| $f_{rep}$ | số xung phát mỗi giây |
| $P_{click}$ | tỉ lệ xung tạo được một click ở Bob |
| $q$ | tỉ lệ click **trùng cơ sở đo** (sống sót qua bước sàng) |
| $1 - 2H_2(e)$ | tỉ lệ còn lại sau **sửa lỗi** ($H_2$) và **khuếch đại riêng tư** ($H_2$) |

$q = 1/2$ khi hai cơ sở dùng đều nhau; $q = p_z^2 + p_x^2$ khi lệch cơ sở.
$R = 0$ khi QBER $\ge$ **11%** — nghiệm của $1 - 2H_2(e) = 0$, chính là ngưỡng
Shor–Preskill của BB84 **không dùng decoy**. Trong bảng kết quả, cột `SKR/xung`
là $R/f_{rep}$, tức bit khóa trên mỗi xung phát.

> ⚠ **(21) không có phạt PNS.** Nó là giới hạn tiệm cận lý tưởng ($f = 1$). Nâng
> $\mu$ làm $R$ tăng gần tuyến tính mà công thức **không tính tiền** cho phần đa
> photon Eve tách được. Xem [mục 7.3](#73-chỗ-lệch-cần-quyết-định-trước-khi-viết-bài)
> — đây là chỗ phản biện sẽ bắt.

### 2.7 Pha adaptive — khi $L$ và $\mu$ cũng có chỉ số thời gian

Ở pha `fixed`, $\lambda$ và $\mu$ cố định nên (14) đủ dùng. Ở pha `adaptive`,
**bộ điều khiển tự đổi chúng giữa các khối**, nên phải tách rõ hai loại đại lượng:

$$\underbrace{h_f[k]}_{\text{ngẫu nhiên, ngoại sinh}} \qquad\text{và}\qquad \underbrace{\big(\lambda[k],\ m[k],\ g[k]\big)}_{\text{điều khiển, nội sinh}}$$

$$\bar n[k] = g[k]\cdot\underbrace{\frac{m[k]}{8}\,\mu_{nom}}_{\mu[k]}\cdot h_\ell\big(d,\ \lambda[k];w\big)\cdot h_f[k]\cdot\eta_{det} \tag{22}$$

$$P_{click}[k] = g[k]\cdot\Big[1 - (1-Y_0)\,e^{-\bar n[k]}\Big], \qquad e_{pol}[k] = e_{pol}\big(d,\lambda[k]\big) \tag{23}$$

Luật điều khiển là một hàm của **quá khứ**, không phải của hiện tại:

$$\big(\lambda[k],\, m[k],\, g[k]\big) = \pi\big(\mathcal{F}_{k-1}\big), \qquad \mathcal{F}_{k-1} = \sigma\Big\{\text{qber}[j],\ \text{snr\_level}[j],\ \text{qber\_jitter}[j],\ \text{window\_valid}[j]\ :\ j \le k-1\Big\} \tag{24}$$

Ba điều (22)–(24) nói ra mà lời văn không nói được:

1. **$\lambda[k]$ vào hai chỗ** — cả $h_\ell$ (qua $c(\lambda)$) lẫn $e_{pol}$ (qua
   $b(\lambda)$). Trong RTL đúng là hai ROM cùng địa chỉ `{lam, water}`.
2. **$\mu$ vào theo bậc $1/8$** — RTL làm `psig = (psig · m) >> 3`, với $m$ danh
   định 8 và trần `MU_CAP = 12` ([adaptive_controller.v:45](verilog/adaptive_controller.v#L45)).
   Nên **tỉ số cường độ tối đa so với pha fixed là đúng $12/8 = 1.5$**.
3. **Kết hợp (24) với (0b): $h_f[k] \perp \mathcal{F}_{k-1}$.** Bộ điều khiển
   không thể dự đoán fade kế tiếp. Nó chỉ học được tính chất *dừng* — λ nào tốt,
   kênh xấu tới mức nào — chứ không cưỡi được từng nhịp fading.

> ⚠ **TRẠNG THÁI THỰC CỦA $g[k]$: ở chế độ PC thì $g[k] \equiv 1$.**
>
> `tx_permitted` chỉ có **một** nơi tiêu thụ, [top_module.v:674](verilog/top_module.v#L674),
> nằm trong nhánh `else if` chỉ chạy khi `!pc_input_mode`. Ở chế độ PC (`SW[9]=1`
> — đúng cấu hình đã thu **toàn bộ** số liệu), FSM đi
> `FSM_IDLE → FSM_WAIT_CMD → FSM_ENCODE` và **không hề kiểm tra** `tx_permitted`.
> Đồng thời ở PAUSE **do quyết định trên cửa sổ hợp lệ**, bộ điều khiển đặt
> `power_level <= CON_POWER = MU_CAP = 12`, tức cường độ **cao nhất**, không phải 0
> ([adaptive_controller.v:416-421](verilog/adaptive_controller.v#L416-L421)).
> (Đường PAUSE còn lại — link chết vì `stale_windows` — không đụng `power_level`;
> hai đường phân biệt bằng cột `mu`, xem [mục 1](#pha---phase).)
>
> Số liệu tự xác nhận: `clicks_adaptive_A_dist_d8_L3.csv` (45 m) có **1535 dòng
> click mang `mode = 3`**, tất cả ở μ = 12. Nếu PAUSE thật sự cho 0 click thì
> `mode = 3` **không thể xuất hiện** trong một file log click.
>
> Vậy "94.4 % PAUSE" **không** có nghĩa "bộ điều khiển từ chối phát 94 % thời
> gian". Nó có nghĩa: *94 % số click đến trong lúc bộ điều khiển tuyên bố PAUSE
> mà vẫn phát ở cường độ tối đa.* Hệ quả: phần tăng $P_{click}$ đo được ở 45 m là
> **1.510×**, còn tỉ số μ thuần là **1.500×** — toàn bộ "adaptive gain" ở cự ly
> xa là nút cường độ. Phải sửa RTL rồi đo lại, hoặc trình bày PAUSE như *trạng
> thái cảnh báo được ghi nhận* chứ không phải hành động.

**(22)–(23) đã được kiểm bằng số liệu.** Đảo tỉ lệ click theo từng ô $(\lambda,m)$
rồi dựng lại $P_{click}$ và QBER cho cả 31 điểm adaptive: tỉ số gộp
đo/dự đoán = **0.987**, theo điểm 0.998 ± 0.049. Chấm cùng số liệu đó bằng (14)
với λ = 450, μ = 8 thì ra 1.284. Chi tiết và công thức đảo ở
[§3.5.1](#351-pha-adaptive--kiểm-2223-và-vì-sao-phải-kiểm-khác-đi). Nói cách khác
$m[k]$ và $\lambda[k]$ trong (22) là **đủ** để giải thích toàn bộ chênh lệch giữa
hai pha — không còn phần dư nào để gán cho "bộ điều khiển thông minh".

Chỗ $\lambda[k]$ chứng minh được giá trị của mình là **nước đục**, nơi $c(\lambda)$
đảo thứ tự. Mô hình ở harbor 1.5 m, L3: 450 nm cho $P_{click} = 4.280\times10^{-4}$,
532 nm $1.115\times10^{-3}$, 650 nm $1.470\times10^{-3}$ — tức 650 nm hơn 450 nm
**3.44×**. Đo được: 75 % số click ở 650 nm và mức tăng so với pha fixed là 3.08×,
trong khi tỉ số μ chỉ giải thích được 1.41×. Đối chiếu với mục A ở 45 m, nơi mức
tăng 1.51× nằm gọn trong tỉ số μ 1.50× và **không** còn chỗ cho λ.

> Phản ví dụ phải nêu kèm: ở harbor **2 m**, tối ưu là 650 nm với biên 4.91×,
> nhưng bộ leo đồi đứng nguyên ở **100 % 450 nm** với μ ghim 11.9 — mức tăng 1.44×
> đúng bằng tỉ số μ. Ứng viên λ ở đó hiếm khi qua nổi `window_valid` trong
> `LAM_ACC` cửa sổ, nên bộ điều khiển **mất khả năng dò λ đúng ở chỗ cần nhất**.
> Đây là giới hạn của bộ điều khiển, không phải của số liệu.

### 2.8 Từ mô hình liên tục xuống số nguyên RTL

Phần này là cầu nối chứng minh "emulator tái tạo đúng mô hình" — luận điểm chính
của repo, nên công thức phải có trong bài.

**Thang lượng tử hóa** ([uwoc_lut_gen.py:70-80](python/uwoc_lut_gen.py#L70-L80)):

| Đại lượng | Bề rộng | Quy ước | Vì sao |
|---|---|---|---|
| $h_s, h_o$ | 12 bit | `H_MEAN = 256` ↔ $h=1.0$, biểu diễn $h\in[0,16)$ | đuôi Gamma/Weibull dưới nước rất nặng, $h_{max}$ tới 16–20; kẹp ở 8 bit/128 làm $\mathbb{E}[h]$ sụp từ 1.00 xuống 0.56 |
| xác suất | 24 bit | $p \leftrightarrow \mathrm{round}(p\cdot 2^{24})$ | $P_{sig}$ xuống $\sim10^{-7}$ ở cự ly xa; ở 16 bit nó **làm tròn về 0** và tín hiệu biến mất hoàn toàn |

**Chuỗi số nguyên mà RTL thực thi** ([uwoc_channel.v](verilog/uwoc_channel.v), §4):

$$h_f^{\text{int}} = \min\!\left(\left\lfloor \frac{h_s^{\text{int}} \cdot h_o^{\text{int}}}{2^8} \right\rfloor,\ H_{MAX}\right) \tag{25}$$

$$p_{sig}^{\text{int}} = \min\!\left(\left\lfloor\frac{1}{2^3}\left\lfloor \frac{p_{ref}^{\text{int}}\cdot h_f^{\text{int}}}{2^8}\right\rfloor \cdot m \right\rfloor,\ P_{MAX}\right) \tag{26}$$

$$\text{click} = \big[u_1 < p_{sig}\big] \ \vee\ \big[u_2 < p_{noise}\big], \qquad \text{err} = \begin{cases} [u_3 < e_{pol}] & \text{nếu click tín hiệu}\\ [u_3 < \tfrac12] & \text{nếu chỉ click nền}\end{cases} \tag{27}$$

với $u_i$ là số ngẫu nhiên 24 bit đều. **(27) tương đương chính xác với (18)
nhưng không cần phép chia** — đó là lý do nó tổng hợp được lên FPGA.

**Ba chỗ phần cứng LỆCH khỏi mô hình liên tục** — phải khai báo, nếu không thì
mọi sai lệch đo được sẽ bị quy oan cho RTL:

1. **$\sigma_{ho}^2$ bị lượng tử hóa lên thang bậc 4×.** `ho_rom` chỉ sinh ở cự
   ly tham chiếu 20 m; phụ thuộc cự ly được mang bằng một **độ dời mức nguyên**:

   $$\text{offset}(d) = \mathrm{clip}\!\left(\mathrm{round}\!\left(\log_4\frac{\sigma_{ho}^2(d)}{\sigma_{ho}^2(20\,\text{m})}\right),\ -3,\ 3\right), \qquad \text{eff\_level} = \mathrm{clip}\big(\text{turb}+\text{offset},\ 0,\ 5\big)$$

   Nên $\sigma_{ho}^2$ trên board rơi vào thang rời rạc $\{0.02, 0.08, 0.30,
   1.00, 3.00\}$. Ví dụ ở 25 m offset = 0, board rút L4 từ $\sigma_{ho}^2=1.00$
   trong khi mô hình liên tục nói 1.55 — **lệch 55 % về phương sai**, rơi đúng
   vào đuôi fade sâu quyết định outage. Vì vậy bảng theo khối phải so với
   `rom_channel()` ([sim_table.py:119](python/sim_table.py#L119)), không so với
   mô hình liên tục.
2. **$\sigma_s^2$ bị gom vào 8 lớp** `HS_CLASS_SIGMA2`.
3. **Trường `irrad` báo về chỉ 8 bit** (128 ↔ 1.0), **bão hòa ở $h = 1.99$**. Ở
   L5 phần lớn phân bố vượt trần, nên CV tính từ cột này **ước lượng thiếu** độ
   tán. Dùng thống kê QBER theo khối (`--blocks`) thay thế.

---

## 3. Đại lượng đo và thống kê

### 3.1 Định nghĩa các cột

| Cột | Công thức | Nghĩa |
|---|---|---|
| `n_qubit` | — | số lệnh qubit PC đã gửi |
| `n_click` | — | số dòng báo cáo nhận được (mỗi click một dòng) |
| `n_sift` | — | số click **trùng cơ sở đo** giữa Alice và Bob |
| `n_err` | — | số bit sàng bị sai |
| `p_click` | `n_click / n_qubit` | so trực tiếp với `p_click_model` |
| `sift_eff` | `n_sift / n_qubit` | ≈ `½ · P_click` khi hai cơ sở dùng đều |
| `qber` | `n_err / n_sift` | **ước lượng điểm** |
| `qber_hi` | Clopper–Pearson một phía 95% | **cận trên** |
| `secure` | `n_sift ≥ 16` **và** `qber_hi < 0.11` | |
| `skr_per_pulse` | `sift_eff · max(0, 1−2H₂(qber_hi))` | dùng **cận trên**, bi quan |

Hai chỗ dễ đọc nhầm:

**`qber` không phải kết quả, `qber_hi` mới là.** Đánh giá an toàn dùng cận trên,
không dùng ước lượng điểm — mọi bit Eve có thể đã lấy đều bị tính. `skr_per_pulse`
cũng vậy.

**`n_sift < 16` nghĩa là không kết luận.** `MIN_SIFT = 16` khớp với tham số cùng
tên trong [channel_monitor.v](verilog/channel_monitor.v). Không có ngưỡng này thì
một điểm đo xa sẽ báo "QBER = 0%, an toàn" chỉ vì đúng một photon tới nơi.

### 3.2 Vì sao QBER đo nhảy lung tung

Ký hiệu trong cả mục 3: $x = n_{err}$ (số lỗi), $n = n_{sift}$ (số phép thử),
$e = x/n$ (QBER ước lượng điểm). QBER là ước lượng nhị thức, sai số chuẩn:

$$\sigma_e = \sqrt{\frac{e\,(1-e)}{n}} \tag{28}$$

`sift_eff` giảm khoảng 2 bậc độ lớn từ 5 m tới 35 m, nên nếu để `batch` cố định
thì $n$ sụp theo và **thanh sai số phình nhanh hơn nhiều so với tốc độ tăng của
chính QBER**. Xu hướng bị chôn dưới nhiễu lấy mẫu. Đó là lý do phải đặt mục tiêu
theo $n_{sift}$ chứ không theo số qubit.

Ví dụ cụ thể: 0 lỗi trên 93 bit sàng cho ước lượng Wald là "0.00 % ± 0.00 %",
trong khi cận trên thật là 3.17 %. Công thức (28) **sụp đổ hoàn toàn tại $e=0$** —
đó là lý do phải dùng (29).

### 3.3 Khoảng Clopper–Pearson

Chính xác, không phải xấp xỉ chuẩn — bắt buộc ở đây vì $x$ thường bằng 0 hoặc 1,
vùng mà xấp xỉ Wald cho khoảng rộng bằng 0.

Cận trên một phía, mức tin cậy `conf` (đây là con số dùng để **kết luận bảo mật**):

$$e_{hi} = \text{BetaInv}\big(\text{conf};\ x+1,\ n-x\big) \tag{29a}$$

Hai phía, dùng cho thanh sai số trên hình:

$$e_{lo} = \text{BetaInv}\Big(\tfrac{1-\text{conf}}{2};\ x,\ n-x+1\Big), \qquad e_{hi} = \text{BetaInv}\Big(\tfrac{1+\text{conf}}{2};\ x+1,\ n-x\Big) \tag{29b}$$

Quy ước biên: $x = 0 \Rightarrow e_{lo} = 0$; $x = n \Rightarrow e_{hi} = 1$
([sim_table.py:104-111](python/sim_table.py#L104-L111)).

#### 3.3.1 QBER "gộp" và QBER "theo khối" là HAI đại lượng khác nhau

Đây là chỗ dễ kết luận sai nhất trong cả dự án, và là toán đứng sau kết quả mục B.

Gọi $s_k$ = số bit sàng của khối $k$, $x_k$ = số lỗi của khối đó, $B$ = số khối:

$$\underbrace{e_{\text{gộp}} = \frac{\sum_k x_k}{\sum_k s_k} = \sum_k w_k\, e_k,\quad w_k = \frac{s_k}{\sum_j s_j}}_{\text{trọng số theo SỐ CLICK của chính khối đó}} \qquad\ne\qquad \underbrace{\bar e_{\text{khối}} = \frac{1}{B}\sum_k e_k}_{\text{trọng số ĐỀU}} \tag{30}$$

Vì $s_k \propto h_f[k]$ gần đúng, trọng số $w_k$ **tỉ lệ với chính độ sáng của
khối**. Khối fade sâu — khối có QBER cao nhất — lại gần như **không đóng góp**
vào con số quyết định độ an toàn của chính nó. Cộng với (19), ta có lời giải
thích đầy đủ cho bảng đo được ở 25 m:

| Mức | $e_{\text{gộp}}$ | $\bar e_{\text{khối}}$ | std theo khối | outage |
|---|---:|---:|---:|---:|
| L1 | 3.72 % | 3.71 % | 2.84 % | 0.013 |
| L3 | 3.74 % | 3.70 % | 3.48 % | 0.031 |
| L5 | 3.49 % | **13.89 %** | **24.53 %** | **0.250** |

Cột "gộp" phẳng vì **hai** cơ chế cộng lại: (19) làm kỳ vọng triệt tiêu fading,
và (30) làm phép gộp tự đánh trọng số thiên về khối sáng. **Báo cáo $e_{\text{gộp}}$
rồi kết luận "nhiễu loạn không ảnh hưởng" là sai** — đại lượng đúng để báo cáo là
$\bar e_{\text{khối}}$, độ lệch chuẩn của nó, và outage.

→ `qber_upper()` [bb84_uwoc_measure.py:268](python/bb84_uwoc_measure.py#L268),
`cp_interval()` [paper_figs_uwoc.py:68](python/paper_figs_uwoc.py#L68),
[sim_table.py:104](python/sim_table.py#L104)

### 3.4 Kiểm định đối chiếu mô hình

[check_vs_theory.py](python/check_vs_theory.py) chạy hai phép kiểm.

**Kiểm định 1 — số click.** So $n_{click}$ đo được với kỳ vọng
$\mathbb{E} = N\,p$, trong đó $N = n_{qubit}$ và $p = $ `p_click_model`. Kiểm tra
suy hao Beer–Lambert, hình học và fading cùng lúc.

**Kiểm định 2 — số lỗi.** Kiểm tra `qber_model` có nằm trong khoảng CP 95 % (29b)
của điểm đo không. Kiểm tra $e_{pol}(d)$ và nền $Y_0$.

Đọc kết quả: hàng **GỘP** mới là phép kiểm có sức phân giải. Với 10 điểm chạy
song song, kỳ vọng ~0.5 điểm có $p < 0.05$ **ngay cả khi mô hình hoàn toàn đúng**
— một điểm lẻ lệch không nói lên gì, phải xem nó có lặp lại ở phiên đo dài hơn không.

#### 3.4.1 Phương sai số click có HAI số hạng — Poisson thuần là SAI

Đây là phần phương pháp luận đáng đưa vào bài: **cách kiểm định thống kê một
emulator kênh khi fading tương quan theo khối.**

Chia $N$ lần phát thành $B = N/N_{coh}$ khối; trong khối $k$ thì $h_f[k]$ đóng
băng nên xác suất click có điều kiện là $p\,h_f[k]$ (chế độ tuyến tính, xem (19)).
Dùng luật phương sai toàn phần $\mathrm{Var}(n) = \mathbb{E}\big[\mathrm{Var}(n\mid h)\big] + \mathrm{Var}\big(\mathbb{E}[n\mid h]\big)$:

$$\mathbb{E}\big[\mathrm{Var}(n\mid h)\big] \approx \sum_{k=1}^{B}\frac{N}{B}\,p = N p, \qquad \mathrm{Var}\big(\mathbb{E}[n\mid h]\big) = \mathrm{Var}\!\left(\frac{N}{B}p\sum_k h_f[k]\right) = \left(\frac{N p}{B}\right)^{\!2} B\,\sigma_h^2$$

$$\boxed{\ \mathrm{Var}\big(n_{click}\big) = \underbrace{N p}_{\text{nhiễu đếm}} \;+\; \underbrace{\frac{(N p)^2\,\sigma_h^2}{B}}_{\text{fading: chỉ có } B \text{ mẫu độc lập}}\ } \tag{31}$$

$$z = \frac{n_{click} - N p}{\sqrt{\mathrm{Var}(n_{click})}} \tag{32}$$

với $\sigma_h^2$ lấy từ (10). Đọc (31) như sau: số hạng thứ hai chia cho $B$ vì
trung bình hóa $B$ mẫu fading độc lập; **$B$ càng nhỏ thì fading càng chi phối**.

- `coh_sel = 0`: $B \sim 10^5$ → số hạng fading biến mất, Poisson thuần đúng.
- `coh_sel = 11`: một điểm 5 m chỉ trải ~25 khối → số hạng fading **chi phối**.

Hậu quả cụ thể, lấy đúng dòng `fixed_A_dist_d2_L3` (15 m, $B \approx 48.5$ khối,
$\sigma_h^2 = 0.166$): chấm bằng Poisson thuần ra **−11.9σ** ("hỏng nặng"), chấm
đủ hai số hạng ra **−1.9σ** ("bình thường"). Cùng một số liệu, hai kết luận trái
ngược — khác biệt duy nhất là dùng đúng (31).

> `sim_table.py --compare` tính đủ cả hai số hạng
> ([sim_table.py:329-335](python/sim_table.py#L329-L335)) và in cảnh báo khi có
> điểm trải < 100 khối; `check_vs_theory.py` thì chưa. **Khi hai script cho z
> khác nhau, tin `sim_table.py`.**

#### 3.4.2 Ngân sách đo phải khớp với đại lượng cần đo

Hệ quả trực tiếp của (30)–(31), và là một lỗi đã thật sự xảy ra trong dự án:

| Đại lượng cần đo | Dừng theo | Vì sao |
|---|---|---|
| QBER (một con số) | $n_{sift}$ | độ chính xác do (28) quyết định |
| **độ tán / outage** (mục B) | **số lần phát** | dừng theo $n_{sift}$ **tương quan với chính fading** |

Quy tắc "dừng khi đủ $N$ bit sàng" làm điểm nào mở đầu vào đoạn kênh sáng thì đạt
chỉ tiêu sớm rồi dừng ngay ở đó → mẫu thiên về khối $h_f$ cao → **độ tán bị hạ
thấp**. Lần chạy mục B đầu tiên đúng như vậy: L5 đạt 6000 bit sàng trong 129 khối
trong khi L1 cần 154 — mức nhiễu loạn mạnh nhất lại cho mẫu **nhỏ nhất và đẹp
nhất**, ngược hoàn toàn với vật lý. Nay mục B dùng `target_qubit`
([fpga_collect.py:148](python/fpga_collect.py#L148)).

### 3.5 Kết quả đối chiếu hiện tại

Chiến dịch đo khép lại 2026-08-13: **67 điểm**, 36 `fixed` + 31 `adaptive`,
**4.213×10⁸** lần phát, 389 325 click, 194 590 bit sàng, 34.0 giờ.

**Pha `fixed` — kiểm (16) và (18).** Gộp 36 điểm: **2.373×10⁸** lần phát,
**184 217** click so với **187 707** kỳ vọng → tỉ số **0.981**, mỗi điểm lẻ nằm
trong 0.81–1.13 trên hai bậc độ lớn của `P_click`. Đây mới là luận điểm chính của
repo — emulator tái tạo đúng vật lý — và nó mạnh hơn hẳn phép kiểm QBER.

#### 3.5.1 Pha `adaptive` — kiểm (22)–(23), và vì sao phải kiểm khác đi

Không so được thẳng như pha `fixed`, vì cột `p_click_model` trong `fpga_points.csv`
tính bằng `model_expect()` ([fpga_collect.py:468](python/fpga_collect.py#L468)) —
dùng `LinkConfig(lam_nm=lam_nm)`, tức **λ mà PC yêu cầu và μ danh định 8**. Ở pha
adaptive thì cả hai đều sai: bộ điều khiển đã đổi chúng. Gộp 31 điểm adaptive theo
cột đó ra tỉ số **1.284** — con số này **không** phải sai số mô hình, nó là hệ quả
của việc chấm bằng công thức (14) trong khi số liệu tuân theo (22).

Cách kiểm đúng, dùng chính telemetry từng click. Gọi $s_c$ là tỉ lệ click rơi vào
ô $c = (\lambda, m)$ và $P_c$, $Q_c$ là giá trị mô hình của ô đó — tính bằng (22)
với $\mu_c = \tfrac{m}{8}\mu_{nom}$ và $h_\ell(d,\lambda_c;w)$. Vì $s_c$ lấy
**điều kiện đã có click**, tỉ lệ *lần phát* của ô $c$ tỉ lệ với $s_c/P_c$, nên:

$$P_{click}^{\text{dự đoán}} = \left(\sum_c \frac{s_c}{P_c}\right)^{\!-1}, \qquad \text{QBER}^{\text{dự đoán}} = \sum_c s_c\,Q_c \tag{33}$$

QBER thì lấy trung bình có trọng số theo click thẳng, không cần đảo, vì bản thân
QBER đã là đại lượng *trên mỗi click*.

Kết quả trên 31 điểm adaptive:

| Cách chấm | Tỉ số gộp `click đo / click dự đoán` |
|---|---:|
| Theo (14), λ = 450 và μ = 8 — tức cột `p_click_model` | 1.284 |
| **Theo (22)–(23) với (λ, μ) thật của từng click** | **0.987** |

Trung bình theo điểm **0.998**, độ lệch chuẩn **0.049**, dải **[0.897, 1.105]** —
đúng cùng một dải với pha `fixed`. Số lỗi gộp: 3903 đo / 3838 dự đoán = **1.017**.
→ chạy lại bằng `python python/check_adaptive_formula.py`, nó in cả hai cách chấm
cạnh nhau.

**Nghĩa là:** toàn bộ 28 % "tăng thêm" của pha adaptive được (22) giải thích hết
bằng λ và μ, không còn dư lượng nào phải quy cho bộ điều khiển hay cho RTL. Đây là
phép kiểm mạnh hơn phép kiểm pha `fixed`, vì nó ràng buộc thêm hai bậc tự do mà
`fixed` không có.

> ⚠ **Phép kiểm này MÙ với $g[k]$.** (33) chỉ đọc được các ô có click, nên nếu
> PAUSE thật sự ngắt phát thì những lần phát đó biến mất khỏi cả tử số lẫn mẫu số
> và tỉ số vẫn ra 1. Nó **nhất quán** với $g\equiv 1$ ([§2.7](#27-pha-adaptive--khi-l-và-μ-cũng-có-chỉ-số-thời-gian))
> chứ không chứng minh được điều đó. Chứng minh $g\equiv 1$ nằm ở chỗ khác: đọc
> RTL, và sự tồn tại của các dòng click mang `mode = 3`.

---

## 4. Cách đọc file `fpga_points.csv`

File này có **25 cột**. Không phải cột nào cũng đáng nhìn — dưới đây là thứ tự đọc
và ý nghĩa của từng cột.

### 4.1 Đọc theo bốn bước, đúng thứ tự này

Đừng đọc từ trái sang phải. Đọc theo mức độ ưu tiên, vì bước sau chỉ có nghĩa
khi bước trước đã đạt.

**Bước 1 — Dòng này có đáng tin không?** Nhìn `n_sift`.

Dưới 16 thì dừng lại, mọi thứ còn lại trong dòng đó vô nghĩa. Không phải "kênh
tốt", không phải "kênh xấu" — là **chưa đo được**. Trên hình, những điểm này
phải vẽ bằng mũi tên cận trên, không vẽ như điểm đo.

**Bước 2 — Bộ mô phỏng phần cứng có đúng vật lý không?** So `p_click` với
`p_click_model`.

Đây là cột quan trọng nhất của cả file, và là điều bài báo phải chứng minh:
emulator FPGA tái tạo đúng kênh, không chỉ là chạy được. Tỉ số nên nằm quanh
1.0. Phép kiểm này **mạnh hơn hẳn** phép kiểm QBER vì `n_click` lớn hơn `n_sift`
hàng chục lần, nên nó bắt lỗi sớm hơn nhiều.

> ⚠ **Bước 2 chỉ đúng cho dòng `phase = fixed`.** `p_click_model` ghi bằng
> `model_expect()` ([fpga_collect.py:468](python/fpga_collect.py#L468)), tính với
> **λ mà PC yêu cầu và μ danh định 8** — tức công thức (14). Ở dòng adaptive thì
> bộ điều khiển đã đổi cả hai, nên tỉ số gộp ra **1.284** mà emulator vẫn hoàn
> toàn đúng. Muốn chấm dòng adaptive phải dùng (33) với `mu`/`lam_idx` của từng
> click; làm đúng thì ra 0.987
> ([§3.5.1](#351-pha-adaptive--kiểm-2223-và-vì-sao-phải-kiểm-khác-đi)). Đừng bao
> giờ đọc `p_click / p_click_model` của một dòng adaptive như một sai số mô hình.

**Bước 3 — Liên kết có an toàn không?** Nhìn `qber_hi`, không nhìn `qber`.

`qber` chỉ là ước lượng điểm. Kết luận bảo mật dùng cận trên: mọi bit Eve có thể
đã lấy đều phải bị tính. Cột `secure` chính là `n_sift ≥ 16` **và** `qber_hi < 0.11`.

**Bước 4 — Sổ sách tốc độ.** `rate_qps` và `seconds`, chỉ để biết phiên đo có
chạy đúng tốc độ không.

### 4.2 Từng cột

**Nhóm định danh** — dùng để lọc, không mang thông tin vật lý:

| Cột | Ví dụ | Ghi chú |
|---|---|---|
| `tag` | `fixed_A_dist_d2_L3` | khóa checkpoint, duy nhất |
| `phase` | `fixed` | lọc khi vẽ hình so sánh fixed ↔ adaptive |
| `water` | `clear_ocean` | |
| `dist_idx` | `2` | chỉ số trong lưới, **không phải mét** |
| `distance_m` | `15.0` | mét thật, lấy từ `d_grid[dist_idx]` |
| `turb` | `3` | mức L1…L5 |
| `lam_nm` | `450` | |
| `timestamp` | `2026-08-08 12:20:00` | dùng khi cần tìm điểm nào đo trước/sau khi chỉnh phần cứng, hoặc đo bằng bitstream nào |

**Nhóm cấu hình khối kết hợp** — ba cột thêm từ **[v12]**, thiếu chúng thì thống
kê theo khối không dựng lại được:

| Cột | Ví dụ | Nghĩa |
|---|---|---|
| `coh_sel` | `11` | giá trị gửi qua byte `0x60`; 0 = bộ đếm nhịp đồng hồ kiểu cũ |
| `coh_qubits` | `65536` | `2^(coh_sel+5)` — số lần phát mà `h` bị đóng băng. `attempt // coh_qubits` là chỉ số khối |
| `dyn_walk` | `False` | mức nhiễu loạn có tự đi ngẫu nhiên ±1 hay không. Phải `False` cho mọi số liệu công bố |

**Nhóm đếm thô** — đây là số liệu gốc, mọi cột còn lại đều suy ra từ đây. Khi
nghi ngờ điều gì, quay về bốn cột này:

| Cột | Nghĩa |
|---|---|
| `n_qubit` | số lệnh qubit PC đã gửi |
| `n_click` | số click (số dòng báo cáo nhận được) |
| `n_sift` | số click trùng cơ sở đo |
| `n_err` | số bit sàng sai |

**Nhóm dẫn xuất** — tiện lợi, nhưng đều tính lại được từ nhóm trên:

| Cột | Công thức |
|---|---|
| `p_click` | `n_click / n_qubit` |
| `sift_eff` | `n_sift / n_qubit` ≈ `½ · p_click` |
| `qber` | `n_err / n_sift` |
| `qber_hi` | Clopper–Pearson một phía 95% |
| `secure` | `n_sift ≥ 16` và `qber_hi < 0.11` |
| `skr_per_pulse` | `sift_eff · max(0, 1−2H₂(qber_hi))` |

**Nhóm đối chiếu** — giá trị mô hình tính tại đúng cấu hình của dòng đó, ghi
cùng lúc đo để về sau không phải tính lại:

| Cột | So với |
|---|---|
| `p_click_model` | `p_click` — **chỉ có nghĩa ở dòng `fixed`**, vì nó tính với λ do PC đặt và μ = 8 |
| `qber_model` | `qber` và khoảng CP — cùng cảnh báo trên |

**Nhóm vận hành:**

| Cột | Nghĩa |
|---|---|
| `seconds` | thời gian thực đo điểm này |
| `rate_qps` | `n_qubit / seconds` |

### 4.3 Đọc thử một dòng thật

Dòng thật, lấy nguyên từ `data/fpga_points.csv`:

```
tag            fixed_A_dist_d2_L3   distance_m  15.0    turb  3    lam_nm 450
n_qubit        3 179 360            n_click     9902    n_sift 5000  n_err 137
p_click        3.114e-03            p_click_model  3.511e-03
qber           2.74%                qber_model     2.68%
qber_hi        3.15%                secure         True
skr_per_pulse  9.376e-04            seconds  890.1   rate_qps  3572
coh_sel        11                   coh_qubits  65536   dyn_walk  False
```

Đọc theo bốn bước:

1. `n_sift = 5000 ≫ 16` → dòng này kết luận được cả về QBER, không chỉ về
   `P_click`.
2. `p_click / p_click_model = 0.887`. Kỳ vọng 11 162 click, được 9 902. Chú ý:
   điểm này chỉ trải `3 179 360 / 65 536 ≈ 48.5` khối kết hợp, nên phương sai
   **không** thuần Poisson — phải cộng số hạng fading `(Np)²σ²_h/B` với
   σ²_h = 0.166 (xem mục 3.4). Chấm bằng Poisson thuần ra **−11.9σ**, tức là "hỏng
   nặng"; chấm đủ hai số hạng ra **−1.9σ**, tức là bình thường. Đây là chỗ dễ kết
   luận sai nhất trong cả file.
3. `qber_hi = 3.15% ≪ 11%` → an toàn, và lần này là **kết luận thật**: khoảng CP
   hai phía [2.31 %, 3.23 %] hẹp, bao trọn mô hình 2.68 %, tức là *xác nhận* chứ
   không chỉ *không mâu thuẫn*.
4. `rate_qps = 3572`, đúng tốc độ `--chunk 32` mong đợi.

So với một dòng cự ly xa, ví dụ `fixed_A_dist_d9_L3` (50 m, `n_sift = 150`,
QBER 26.67 % [19.78, 34.49]): khoảng tin cậy rộng 15 điểm phần trăm, chỉ đủ để
nói "đã vượt ngưỡng", không đủ để trích một con số. Đó là đặc trưng chung của mọi
dòng có `n_sift` nhỏ — và là lý do các điểm xa trong `RANGE_PLAN` cố tình thưa:
chúng tồn tại để **kẹp** chỗ QBER cắt ngưỡng 11 %, không phải để đọc từng điểm.

### 4.4 Dấu hiệu bệnh lý

Bảng tra khi số liệu trông sai. Cột giữa là **cách phân biệt**, vì nhiều bệnh
cho triệu chứng giống nhau ở cột `p_click`.

| Triệu chứng | Phân biệt bằng | Nguyên nhân |
|---|---|---|
| `p_click` cao hơn mô hình vài lần | `n_click/seconds` ghim ở ~250 bất kể `rate_qps` | `SW[4] = 0`, kênh bị bypass — mọi qubit đều click, FPGA bị nghẽn ở trần ~4.4 ms của FSM_REPORT |
| `p_click` ≈ 0.4× mô hình | `LEDG[7]` sáng | FIFO lệnh tràn, FPGA mất lệnh. Hạ `--chunk` hoặc tăng `--qubit-us` |
| `p_click` thấp, **khớp mô hình của một λ khác** | tỉ số lệch phụ thuộc cự ly theo `exp(−Δc·d)` | Pha adaptive: bộ leo đồi **kẹt ở λ sai**. Phân biệt với FIFO tràn ở chỗ FIFO tràn hạ `p_click` theo một hệ số **không phụ thuộc cự ly**. `lambda_diagnosis()` ([fpga_collect.py:474](python/fpga_collect.py#L474)) tự báo |
| `p_click` nằm **giữa** mô hình của λ tốt và λ xấu | cột `lam_idx` trong `clicks_*.csv` đổi giá trị trong cùng một điểm | Bộ leo đồi đang **nhảy λ**; script in ra tỉ lệ thời gian ở λ đúng |
| `p_click` thấp **kèm** `mode` = 3 chiếm đa số **và** `mu` = 12 | `mu` = 12 | PAUSE do quyết định trên cửa sổ hợp lệ. **Không** phải nó đã ngừng phát — ở chế độ PC `tx_permitted` không nối vào đường phát ([§2.7](#27-pha-adaptive--khi-l-và-μ-cũng-có-chỉ-số-thời-gian)); PAUSE loại này ghim μ ở 12 nên `p_click` thực ra **cao hơn** pha fixed đúng 1.5× |
| `mode` = 3 chiếm đa số nhưng `mu` = **9** | `mu` = 9, và `p_click` sát nền `Y₀` | PAUSE do **link chết** (`stale_windows ≥ DEAD_WINDOWS`, [:338-344](verilog/adaptive_controller.v#L338-L344)). Nhánh này không đặt `power_level` nên μ giữ nguyên giá trị cũ. Không có "1.5× nhờ μ" ở đây — đừng cộng nhầm |
| `qber` = 0% ở cự ly xa | `n_sift < 16` | Chưa đo được. Đọc `qber_hi` |
| `qber` = 100% | `n_sift = 1` | Một bit sàng, ngẫu nhiên rơi vào lỗi |
| `rate_qps` ≈ 63 | | Đang đọc kiểu chờ-từng-qubit, `--chunk` chưa có tác dụng |
| `seconds` chạm đúng trần | `n_sift < target_sift` | Điểm bị cắt vì hết giờ, không phải vì đủ mẫu. Bình thường ở cự ly xa |
| `p_click` lệch mạnh **một điểm lẻ** | các điểm khác bình thường | Nhiều khả năng là ngẫu nhiên. 10 điểm thì kỳ vọng ~0.5 điểm có p < 0.05 ngay cả khi mô hình đúng hoàn toàn. Chỉ đáng đào khi lặp lại ở phiên dài hơn |
| z lệch rất lớn ở **các điểm gần** | `n_qubit / coh_qubits < 100` | Đang chấm bằng Poisson thuần trong khi số khối kết hợp quá ít. Xem mục 3.4 |
| cột `mode`/`mu`/`lam_idx` **rỗng** | `timestamp` trước 2026-08-09 | Số liệu thu bằng bitstream trước [v13]. Dùng được cho `P_click`/QBER, không dùng được cho bất kỳ khẳng định nào về bộ điều khiển |

### 4.5 Nên tập trung vào cột nào

Nếu chỉ có thời gian nhìn ba cột:

1. **`n_sift`** — quyết định dòng đó có nói được gì không.
2. **`p_click` so `p_click_model`** — bằng chứng emulator đúng vật lý. Đây là
   luận điểm chính của bài báo, và là cột có sức thống kê mạnh nhất.
3. **`qber_hi`** — kết luận bảo mật.

Ba cột đó, đọc bằng `check_vs_theory.py` và `sim_table.py --compare` thay vì bằng
mắt, vì chúng tự tính z-score và khoảng Clopper–Pearson cho từng dòng lẫn hàng
gộp. **Hàng GỘP mới là phép kiểm có sức phân giải** — từng dòng riêng lẻ hầu như
luôn "không mâu thuẫn" chỉ vì khoảng tin cậy quá rộng.

Cột `qber` trần thì đừng bao giờ trích thẳng vào bài báo mà không kèm khoảng tin cậy.

---

## 5. Bố cục dữ liệu

```
data/
  fpga_points.csv          mỗi điểm đo một dòng (checkpoint theo cột tag), 25 cột
  clicks_<tag>.csv         mỗi click một dòng — attempt, a_data, a_basis, b_basis,
                           bob, bmatch, err, irrad, mode, mu, lam_idx
  sim_table.csv            ← sim_table.py --matrix   (toàn ma trận mô hình)
  compare_table.csv/.md    ← sim_table.py --compare  (đo ↔ mô hình, .md dán thẳng vào bài)
  block_table.csv          ← sim_table.py --blocks   (thống kê theo khối kết hợp)
  <thư mục con>/           các phiên ĐÃ BỊ THAY THẾ, giữ lại để truy vết — CHỈ CÓ
                           TRÊN MÁY, .gitignore chặn nên không lên repo:
                           adaptive_v13_hong/, adaptive_chunk32_hong/, adapt_debug/
                           (bitstream cũ: lam_idx ghim 0, mu ghim 9),
                           dryrun_v12/, B_sifted_budget/ (ngân sách theo bit sàng,
                           đã bị bỏ vì thiên lệch), d8_n300_cu/
Images/
  fig_uwoc_*.png           hình bài báo   ← paper_figs_uwoc.py
  table_uwoc_results.csv/.tex
```

`data/fpga_points.csv` hiện có **67 dòng**: 36 `fixed` (2026-08-08…09) và 31
`adaptive` (2026-08-09…13). Ba bảng dẫn xuất và `Images/` đã dựng lại ngày
2026-08-13 nên phủ đủ cả 67 dòng; đo thêm điểm nào thì phải chạy lại
`sim_table.py` và `paper_figs_uwoc.py`, nếu không điểm mới chỉ nằm trong
`fpga_points.csv` và **âm thầm vắng mặt** ở mọi bảng lẫn mọi hình.

> ⚠ **Không trộn thư mục con với `data/`.** Các phiên trong thư mục con đo bằng
> bitstream khác, tức là **thiết bị khác**. Mọi so sánh fixed ↔ adaptive đều bắc
> qua ranh giới bitstream và phải nói rõ điều đó: `clicks_fixed_A_dist_d0…d7,d9`
> đo ngày 2026-08-08 với bản chưa có `mode`/`mu`/`lam_idx`; riêng
> `fixed_A_dist_d8` và toàn bộ tập adaptive đo bằng **[v14]** từ 2026-08-09.

> `clicks_adaptive_D_coastal_d0_L5.csv` là **điểm thứ 31, nằm ngoài lưới** —
> coastal 2 m đo lại ở L5, chỗ duy nhất trong mục D có mức nhiễu loạn khác L3.
> Nó vô hại vì `pick()` ([paper_figs_uwoc.py:99](python/paper_figs_uwoc.py#L99))
> lọc theo `phase` và hình mục D chỉ lấy pha fixed, nên nó không bao giờ lọt vào
> một đường quét cự ly. Nó cũng nói được một câu: so với L3 thì `P_click` gần như
> không đổi (9.944×10⁻³ → 1.002×10⁻²) trong khi μ̄ đi 9.0 → 9.7 và tỉ lệ λ dịch
> 47/53/0 → 77/23/0 — bộ điều khiển trả lời nhiễu loạn bằng **cường độ**, không
> bằng **màu**.

Các cột trong file click:

| Cột | Nghĩa |
|---|---|
| `attempt` | **[v12]** chỉ số LẦN PHÁT của click này kể từ `0x01`. `attempt // coh_qubits` = chỉ số khối kết hợp. Log cũ ghi nhầm số CLICK vào đây — `sim_table.py --blocks` tự phát hiện và chuyển sang cắt khối theo đoạn `irrad` liên tiếp, kết quả khi đó là **cận dưới** |
| `a_data`…`err` | bit và cơ sở của Alice/Bob, cờ trùng cơ sở, cờ lỗi |
| `irrad` | 8 bit, **128 ↔ h = 1.0**, dưới 30 là fade sâu. Proxy SNR để dựng hình QBER-theo-SNR |
| `mode` | **[v13]** 0 = AGGRESSIVE, 1 = MODERATE, 2 = CONSERVATIVE, 3 = PAUSE |
| `mu` | **[v13]** mức cường độ áp dụng cho chính qubit đó (8 = danh định) |
| `lam_idx` | **[v13]** 0 = 450, 1 = 532, 2 = 650 nm |

> ⚠ **`irrad` KẸP TRẦN ở 255, tức h = 2.0.** Ở nhiễu loạn yếu không có gì chạm
> trần, nhưng σ²_ho = 3 ở L5 đẩy phần lớn phân bố vượt qua, và CV tính từ cột đã
> bị kẹp **ước lượng thiếu** độ tán — nặng. `sim_table.py` in kèm tỉ lệ bão hòa
> để nói thẳng điều đó thay vì báo một con số sai. Thống kê QBER theo khối
> (`--blocks`) không bị kẹp, nên với số liệu [v12] trở đi thì luôn ưu tiên nó.

Luồng chạy:

```
uwoc_channel_model.py   mô hình giải tích + 8 phép tự kiểm
        ↓
uwoc_lut_gen.py         sinh ROM cho FPGA (xác suất thang 2²⁴, h thang 256)
        ↓
[ FPGA ]  ← tb_uwoc_channel.v / tb_adaptive_loop.v / tb_cmd_fifo.v gác cổng
        ↓
fpga_collect.py         thu số liệu → data/fpga_points.csv + clicks_*.csv
        ↓
check_vs_theory.py      kiểm định thống kê nhanh (chấm theo (14) — pha fixed)
check_adaptive_formula.py  chấm pha adaptive theo (22)-(23) + (33)
sim_table.py            ba bảng: mô hình / đo ↔ mô hình / theo khối → data/
paper_figs_uwoc.py      dựng hình → Images/
```

`bb84_uwoc_measure.py` nằm ngoài luồng này: nó quét nhanh để **nhìn**, có chế độ
`--simulate` không cần phần cứng. `fpga_collect.py` chạy lâu để **thu số liệu
công bố được**. `sim_table.py` **không mở cổng COM**, nên chạy được song song với
một phiên đo đang diễn ra.

---

## 6. Giao diện phần cứng

### 6.1 Công tắc

| Công tắc | Chức năng | Giá trị cho phiên đo |
|---|---|---|
| `SW[9]` | nguồn đầu vào | **1** = PC điều khiển qua UART |
| `SW[4]` | bật kênh | **1** = emulator UWOC hoạt động (0 = bypass lý tưởng) |
| `SW[1]` | điều khiển thích ứng | 0 = pha fixed, 1 = pha adaptive |
| `SW[0]` | chế độ chạy | **0** = tự động |
| `SW[7:5]` | mức nhiễu loạn | chỉ là giá trị mặc định lúc reset; ở chế độ PC thì UART đặt |
| `SW[3:2]` | loại nước | như trên |

> `SW[4] = 0` làm **mọi qubit đều click** ([uwoc_channel.v:388-392](verilog/uwoc_channel.v#L388-L392)).
> Triệu chứng: `P_click` cao hơn mô hình nhiều lần, và số dòng/giây bị ghim ở
> ~230 (= 1/4.4 ms, trần của FSM_REPORT) bất kể gửi nhanh chậm.

### 6.2 Đèn báo

| Đèn | Nghĩa |
|---|---|
| `LEDG[3]` | kênh đang bật — **phải sáng** khi đo |
| `LEDG[4]` | photon vừa bị mất |
| `LEDG[5]` | cửa sổ đủ mẫu để tin được |
| `LEDG[6]` | chế độ thích ứng đang bật |
| `LEDG[7]` | **FIFO lệnh đã từng tràn** — nếu sáng thì số liệu đã mất lệnh |

### 6.3 Giao thức UART (PC → FPGA)

Byte có bit[7] = 0 là lệnh cấu hình:

| Byte | Nghĩa |
|---|---|
| `0x01` | xóa thống kê (đồng thời xả FIFO lệnh **và** đặt lại gốc lưới khối kết hợp) |
| `0x02` | yêu cầu báo cáo trạng thái |
| `0x30 \| dist[3:0]` | đặt chỉ số cự ly (0–15 trong lưới của loại nước) |
| `0x40 \| water[1:0]<<2 \| lam[1:0]` | đặt loại nước + bước sóng |
| `0x50 \| turb[2:0]` | đặt mức nhiễu loạn, **giữ cố định** (0x50–0x57) |
| `0x58 \| turb[2:0]` | như trên, nhưng **bật** bước ngẫu nhiên ±1 của mức (0x58–0x5F) |
| `0x60 \| coh[3:0]` | **[v12]** độ dài khối kết hợp (0x60–0x6F) |

Byte có bit[7] = 1 là lệnh qubit: `bit[2] = a_data`, `bit[1] = a_basis`, `bit[0] = b_basis`.

> **Thứ tự gửi có ý nghĩa.** `0x01` phải đi **cuối cùng**: ở bitstream [v12] nó
> đồng thời khởi động lại lưới khối kết hợp trong `uwoc_channel`, để trường
> `total` của mọi dòng báo cáo sau đó và chỉ số khối fading dùng chung một gốc.
> Gửi nó trước các byte cấu hình thì hai thứ lệch nhau đúng bằng số qubit đã chạy
> xen giữa. Xem `Link.configure()`
> ([fpga_collect.py:109](python/fpga_collect.py#L109)).

> **`0x60` — bộ chọn khối kết hợp.** `coh = 0` giữ bộ đếm nhịp đồng hồ kiểu cũ
> (`2^COH_LOG2` chu kỳ); `coh = k ≥ 1` đóng băng `h` trong **2^(k+5) lần phát**.
> Cái mà vật lý cố định là tỉ số không thứ nguyên `N_coh = τ_coh · f_rep` — 50 000
> xung/khối trong mô hình. Bộ đếm theo đồng hồ chỉ tái tạo được điều đó nếu qubit
> thật sự đến ở nhịp `f_rep`; khi PC lái ở ~3500 qubit/s thì board giữ `h` được
> đúng 18 qubit, **thiếu 2726 lần**, và mọi cửa sổ đo đều trung bình hóa qua ~10⁵
> mẫu fading độc lập — tức là nhiễu loạn bị xóa sạch khỏi số liệu. `coh = 11`
> (65 536 qubit) làm một mẫu fading bằng đúng một cửa sổ `channel_monitor`
> (`NEXP_LOG2 = 16`), và đó là mặc định của `fpga_collect.py`.

### 6.4 Định dạng dòng báo cáo (FPGA → PC)

**Dòng mỗi qubit** — **42 byte** (≈3.65 ms @115 200), chỉ phát khi **có click**,
chỉ ở chế độ PC:

```
@a_data,a_basis,b_basis,bob_bit,bmatch,err,irrad,total,sifted,errors,mode,mu,lam*\r\n
```

| Trường | Độ rộng | Nghĩa |
|---|---|---|
| `a_data`…`err` | 1 chữ số thập phân | bit/cơ sở, cờ trùng cơ sở, cờ lỗi |
| `irrad` | 3 thập phân | `h` thang 128 = 1.0, bão hòa ở 255 |
| `total` | **6 hex** | **[v12]** chỉ số LẦN PHÁT (trước đó là 4 hex, bị tràn mỗi 65 536 lần phát — đúng một khối ở `coh = 11`, và host không có cách nào biết) |
| `sifted`, `errors` | 4 hex | tổng lũy kế |
| `mode`, `mu`, `lam` | 1+1+1 | **[v13]** trạng thái bộ điều khiển áp dụng cho chính qubit đó |

`mode`, `mu`, `lam` được **nối thêm vào cuối**, nên các trường 0…9 giữ nguyên vị
trí và mọi parser viết cho [v12] vẫn đọc đúng dòng [v13]/[v14].

**Dòng trạng thái** — 61 byte, bị tắt ở chế độ PC:

```
$QBER,SNR,PHOT,SIFT,PWR,BPROB,SLOT,GAP,MODE,TURB,FADE,IRRAD,TOT,TSFT,TERR*\r\n
```

### 6.5 Thang số của LUT

| Hằng số | Giá trị | Nghĩa |
|---|---|---|
| `PROB_BITS` | 24 | xác suất lưu ở thang 2²⁴ (ở 16 bit thì `p_sig` làm tròn về 0 ở cự ly xa) |
| `H_MEAN` | 256 | 12 bit, 256 ↔ h = 1.0 (cắt còn 8 bit làm E[h] sụp từ 1.00 xuống 0.56) |
| `N_DIST` | 16 | số điểm cự ly mỗi loại nước |
| `N_HS_CLASS` | 8 | số lớp lượng tử hóa của σ_s² |
| `ROM_DEPTH` | 256 | số điểm của mỗi hàm CDF ngược |
| `COH_BASE_LOG2` | 5 | `coh_qubits = 2^(coh_sel + 5)` |
| `TURBO_SLOT` | 500 | khe 10 µs thay cho 5 ms mặc định (chỉ ở chế độ PC) |
| `CMD_DEPTH` | 64 | độ sâu FIFO lệnh (gửi tối đa 32 lệnh một lần) |
| `MIN_SIFT` | 16 | ngưỡng số bit sàng tối thiểu, dùng thống nhất ở Python lẫn `channel_monitor.v` |
| `NEXP_LOG2`, `ATTEMPT_LOG2` | 16 | cửa sổ giám sát 65 536 lần phát; **hai hằng này phải khớp `--window` của `uwoc_lut_gen.py`**, lệch là mọi số đọc SNR bị đổi thang mà không báo lỗi |

---

## 7. Tài liệu tham chiếu và đối chiếu với thư mục `Paper/`

### 7.1 Ánh xạ

| Ref | File trong `Paper/` | Dùng vào đâu |
|---|---|---|
| **[1]** | `2023. FPGA-Based_Implementation_of_an_Underwater_Quantum_Key_Distribution_System_With_BB84_Protocol.pdf` | tham số quang-điện tử của `LinkConfig`; dạng QBER tăng theo cự ly (Fig. 19) |
| **[2]** | `Ergodic_capacity_analysis_of_underwater_FSO_systems_over_scattering-induced_fading_channels...pdf` | **xương sống của mô hình kênh**: eq.(2) `h = L·h_s·h_o`, eq.(3) suy hao, eq.(4a/4b) Gamma/Weibull, eq.(5) σ²_ho, eq.(6) phổ Nikishov, Bảng I/II/IV |
| **[3]** | `Performance_Characterization_of_Relay-Assisted_Wireless_Optical_CDMA_Networks...pdf` | eq.(3),(4) chỉ số nhấp nháy; giá trị Petzold cho harbor |
| **[4]** | *không có trong thư mục* | Nikishov & Nikishov 2000 — phổ chiết suất nước biển. Công thức lấy gián tiếp qua [2] eq.(6) |
| **[5]** | *không có trong thư mục* | Andrews & Phillips — cơ sở lý thuyết Rytov, dùng để biện minh cho `SIGMA2_HO_MAX` |

Hai file còn lại **không nuôi công thức nào** trong code:

- `On_the_Reciprocity_of_Underwater_Turbulent_Channels.pdf` (Guo et al., *IEEE
  Photonics J.* 11(2), 2019) — đo thực nghiệm tính thuận nghịch của nhiễu loạn do
  bọt khí, nhiệt độ, độ mặn. Dùng được ở phần *related work*, và là chỗ dựa thực
  nghiệm nếu sau này muốn bàn tới kênh hai chiều.
- `Precoding_Optimization_for_Rate_Splitting_Enabled_Internet_of_Underwater_Things...pdf`
  — RSMA cho UOWC. Xa đề tài (dự án này không có đa truy nhập), chỉ dùng làm dẫn
  chứng bối cảnh.

`2026-04-14_16-16-28_nckh_seee (1).pdf` là **bài trước của chính nhóm**:
"Real-Time FPGA-Based Adaptive Control for Robust FSO Quantum Key Distribution",
kênh **khí quyển Gamma-Gamma**. Dự án hiện tại thay mô hình khí quyển đó bằng mô
hình dưới nước và giữ nguyên kiến trúc điều khiển thích ứng.

### 7.2 Hằng số đã kiểm chứng ngược từ tài liệu gốc

| Hằng số trong code | Nguồn | Trạng thái |
|---|---|---|
| clear ocean a=0.114, b=0.037, c=0.151 | [2] Bảng I | ✓ khớp |
| coastal a=0.179, b=0.219, c=0.398 | [2] Bảng I | ✓ khớp |
| ε ∈ [10⁻⁸, 10⁻²] m²/s³, χ_T ∈ [10⁻¹⁰, 10⁻⁴] K²/s, η = 10⁻³ m | [2] Bảng II | ✓ khớp |
| `TABLE_IV` σ_s², 8 điểm | [2] Bảng IV | ✓ khớp từng số |
| η_det = 0.18 | [1] §II "efficiency at 405 nm is 18%" | ✓ khớp |
| dark_hz = 60 | [1] §II "SPDs has less than 60 Hz noise" | ✓ khớp (là **cận trên**, code dùng làm giá trị danh định) |
| f_rep = 10 MHz | [1] §III-A "20 ns pulses with the repetition rate of 10 MHz" | ✓ khớp |
| harbor a=0.366, b=1.824 | Petzold, qua [3] | ⚠ [3] có trích Petzold nhưng bảng số nằm dạng ảnh, không trích xuất được từ PDF. Đây là bộ giá trị Petzold turbid harbor tiêu chuẩn, dùng rộng rãi trong tài liệu UWOC |

**Một kiểm chứng độc lập đáng đưa vào bài báo.** Bảng IV của [2] còn cột σ²_ho mà
code **chưa hề dùng tới** — nó chỉ lấy cột σ_s². Vì σ²_ho ∝ χ_T tuyến tính, tỉ số
σ²_ho giữa các cự ly không phụ thuộc χ_T, nên so tỉ số là phép kiểm thuần túy cho
tích phân Nikishov:

| | d | tỉ số theo [2] | tỉ số từ `sigma2_ho()` | lệch |
|---|---|---|---|---|
| Clear ocean | 55 → 65 m | 1.380 | 1.365 | −1.1% |
| | 55 → 67 m | 1.465 | 1.444 | −1.4% |
| | 55 → 70 m | 1.595 | 1.565 | −1.9% |
| Coastal | 27 → 33 m | 1.468 | 1.482 | +1.0% |
| | 27 → 35 m | 1.645 | 1.661 | +1.0% |
| | 27 → 37 m | 1.833 | 1.849 | +0.8% |

Khớp trong 1–2% ở cả hai loại nước. Tích phân số của eq.(5) tái tạo đúng phụ
thuộc cự ly của tài liệu gốc.

> Ngược lại, kiểm chứng σ_s² **không** độc lập: `SIGMA_S_FIT` khớp từ chính 8 điểm
> đó, nên sai lệch ~1% chỉ phản ánh chất lượng khớp hàm mũ, không phải xác nhận.

### 7.3 Chỗ lệch cần quyết định trước khi viết bài

**Công thức SKR khác với bài trước.** Bài khí quyển (`nckh_seee`, eq.7) dùng

$$R = Q\big[1 - f\,H_2(e) - H_2(e)\big], \qquad f = 1.16$$

và nêu rõ ngưỡng bảo mật là **9.81%**. Code UWOC hiện tại
([uwoc_channel_model.py:492](python/uwoc_channel_model.py#L492)) dùng

$$R = q\,f_{rep}\,P_{click}\big[1 - 2H_2(e)\big]$$

tức trường hợp `f = 1`, ngưỡng **11%**. `QBER_LIMIT = 0.11` xuyên suốt cả Python
lẫn `channel_monitor.v`.

Hai bài cùng nhóm mà một bài ngưỡng 9.81%, một bài ngưỡng 11% là chỗ phản biện sẽ
hỏi. Cần chọn một và ghi rõ lý do:

- Giữ `f = 1`: SKR là **giới hạn tiệm cận lý tưởng**; phải nói rõ như vậy.
- Đổi sang `f = 1.16`: sát thực tế hơn và nhất quán với bài trước, nhưng phải sửa
  `skr()` và `QBER_LIMIT` ở cả Python lẫn Verilog rồi **đo lại**, vì ngưỡng an
  toàn nằm trong `channel_monitor.v`.

**Điều chỉnh thích ứng không giống bài trước.** Bài khí quyển quảng cáo tối ưu
đồng thời *mức tín hiệu quang phát* và *độ lệch cơ sở đo*. Ở chế độ PC của dự án
này, cơ sở đo do máy tính cấp nên `adapt_basis_prob` bị vô hiệu hoàn toàn (mục 1).
Luận điểm trung thực cho bài UWOC là bộ điều khiển chọn **λ và công suất** — không
phải độ lệch cơ sở, và cũng không phải "quyền phát": `tx_permitted` không nối vào
đường phát ở chế độ PC.

**⚠ Phần tăng `P_click` của pha adaptive chủ yếu đến từ μ, mà công thức SKR
không tính tiền cho nó.** Đây là chỗ phản biện sẽ bắt ngay, và số liệu đã có sẵn
để họ bắt:

| d [m] | `P_click` fixed | `P_click` adaptive | tăng | μ trung bình (adaptive) |
|---:|---:|---:|---:|---:|
| 5 | 1.078e-02 | 1.139e-02 | 1.06× | 9.90 |
| 15 | 3.114e-03 | 4.718e-03 | 1.52× | 10.62 |
| 25 | 1.218e-03 | 1.518e-03 | 1.25× | 11.33 |
| 35 | 2.595e-04 | 3.666e-04 | 1.41× | 11.65 |
| 45 | 6.560e-05 | 9.906e-05 | 1.51× | 11.97 |

Mục D cũng vậy, trừ **một** chỗ: harbor 1.5 m tăng **3.08×** trong khi tỉ số μ chỉ
là 1.41× — phần dư là λ (75 % click ở 650 nm, biên mô hình 3.44×). Đó là điểm duy
nhất trong cả chiến dịch mà λ chứng minh được giá trị của nó bằng số, nên nếu chọn
cách 3 dưới đây thì **đó là điểm phải trích**.

Pha fixed giữ nguyên `active_power = 8`. Vì
`p_sig = ((psig_ref·h_f)>>8)·mu_level>>3`, phần tăng gần như tuyến tính theo μ.
Trong khi đó `skr()` là tốc độ Shor–Preskill **không decoy**, **không có phạt
PNS** — nâng μ trông như được khóa miễn phí, còn thực tế nó làm tăng tỉ lệ đa
photon mà Eve tách được. Ba cách xử lý, phải chọn một:

1. **So sánh ở μ bằng nhau** — đo lại pha adaptive với `MU_CAP = 8`, khi đó phần
   còn lại đúng là công của λ.
2. **Thêm cận decoy-state** vào `skr()` rồi tính lại cả hai pha.
3. **Đổi luận điểm**: quảng cáo **λ** (không tốn gì về bảo mật), nêu phần tăng
   nhờ μ như một *quan sát* kèm đúng cảnh báo này. **Không** gộp PAUSE vào luận
   điểm này: ở chế độ PC nó không ngắt phát ([§2.7](#27-pha-adaptive--khi-l-và-μ-cũng-có-chỉ-số-thời-gian)),
   nên nó không phải hành động bảo mật mà là trạng thái cảnh báo được ghi nhận.

Cách 3 rẻ nhất và vẫn trung thực; cách 1 mạnh nhất. Cách nào cũng phải nói rõ cột
`mu` lấy điều kiện "đã có click" nên **lệch cao** so với μ trung bình theo lần
phát.

**⚠ Hai pha đo bằng hai bitstream khác nhau.** `clicks_fixed_A_dist_d0…d7,d9` đo
2026-08-08 bằng bản chưa có cột `mode`/`mu`/`lam_idx`; `fixed_A_dist_d8` và toàn
bộ tập adaptive đo từ 2026-08-09 bằng **[v14]**. Mọi khẳng định fixed ↔ adaptive đều
bắc qua ranh giới này và phải ghi rõ. Muốn khép hẳn thì đo lại pha fixed dưới
[v14] — đó là việc rẻ, chỉ mất một phiên.

**Vài chỗ nhỏ nên nêu trong phần tham số:**

- [1] dùng laser **405 nm**; dự án dùng bộ ba 450/532/650 nm để có nút xoay λ. Nên
  nói rõ đây là lựa chọn thiết kế, không phải tái lập [1].
- [1] ghi SPD có **dead time < 45 ns**; code không mô hình hóa. Ở `f_rep` = 10 MHz
  chu kỳ xung là 100 ns > 45 ns nên bỏ qua được, nhưng nên nêu ra.
- `gate_ns = 50` trong khi [1] dùng xung 20 ns. Cửa sổ tách sóng rộng hơn độ rộng
  xung là hợp lý, nhưng `Y₀ = (f_dark + f_bg)·t_gate` tỉ lệ thuận với nó — chọn
  50 ns thay vì 20 ns làm `Y₀` lớn hơn 2.5 lần. Cần nêu căn cứ.
- `bg_hz = 200`, `e0 = 0.01`, `k_s = 0.04`, `theta_div = 1 mrad`, `F = 0.85` là
  **giá trị đặt**, không lấy từ tài liệu nào. `k_s` đặc biệt quan trọng vì nó điều
  khiển toàn bộ độ dốc QBER theo cự ly; phải khớp lại từ số liệu đo thật rồi báo
  cáo giá trị khớp được.

### 7.4 Danh mục đầy đủ

- **[1]** B. Kebapci et al., "FPGA-Based Implementation of an Underwater QKD
  System With BB84 Protocol," *IEEE Photonics J.*, 15(4), 2023.
- **[2]** P. Salcedo-Serrano et al., "Ergodic capacity analysis of underwater FSO
  systems over scattering-induced fading channels in the presence of Weibull
  oceanic turbulence," *IEEE ICC 2022*, pp. 3814–3819.
- **[3]** M. V. Jamali, F. Akhoundi, J. A. Salehi, "Performance Characterization
  of Relay-Assisted Wireless Optical CDMA Networks in Turbulent Underwater
  Channel," *IEEE Trans. Wireless Commun.*, 15(6), 2016.
- **[4]** N. G. Nikishov & V. N. Nikishov, "Spectrum of turbulent fluctuations of
  the sea-water refraction index," *Int. J. Fluid Mech. Res.*, 27, 2000.
- **[5]** L. C. Andrews & R. L. Phillips, *Laser Beam Propagation through Random
  Media*, 2nd ed., SPIE Press, 2005.
- **[6]** Y. Guo et al., "On the Reciprocity of Underwater Turbulent Channels,"
  *IEEE Photonics J.*, 11(2), 2019.
