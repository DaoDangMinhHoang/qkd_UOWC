// ============================================================
// TESTBENCH — vong kin uwoc_channel + channel_monitor + adaptive_controller
// ============================================================
// Kiem chung BUOC 3. Bo qua OOK TX/RX va FSM cua top_module, noi truc tiep
// su kien muc qubit tu kenh vao monitor — du de kiem tra vong dieu khien.
//
// TEST A — SNR chuan hoa: o diem lam viec danh dinh (mu_level = 8 = mu_ref)
//          snr_level phai ~ 128 BAT KE loai nuoc / cu ly. Day chinh la muc
//          dich cua viec chuan hoa: loai bo suy hao tinh exp(-c*d).
// TEST B — cong window_valid: cu ly xa -> qua it click -> window_valid = 0
//          -> controller PHAI GIU NGUYEN mode thay vi doi theo nhieu ban.
// TEST C — pham vi hoat dong: mode phai xau dan khi cu ly tang.
// TEST D — leo doi buoc song: harbor phai hoi tu ve red (lam=2),
//          clear ocean phai giu blue (lam=0).
// ============================================================
`timescale 1ns / 1ps

module tb_adaptive_loop;

    // Cua so rut ngan (2^15) de mo phong nhanh; NEXP_LOG2 van la 16 (kich
    // thuoc cua so da dung khi sinh LUT) va monitor tu bu chenh lech bang
    // dich bit — nho vay KHONG phai sinh lai ROM cho rieng mo phong.
    localparam AW   = 15;
    localparam NEXP = 16;
    localparam integer WIN = (1 << AW);

    reg clk = 1'b0, rst_n = 1'b0;
    always #10 clk = ~clk;

    // ---- cau hinh ----
    reg  [1:0] water     = 2'd0;
    reg  [3:0] dist      = 4'd0;
    reg  [2:0] turb      = 3'd1;
    reg        adaptive  = 1'b0;
    reg  [3:0] man_power = 4'd8;

    // ---- kenh ----
    reg         sample_en = 1'b0;
    wire        click, no_click, err_inject;
    wire [15:0] nexp_inv;
    wire [2:0]  cur_level;
    wire [11:0] h_s, h_o, h_f;

    // ---- controller -> kenh ----
    wire [3:0] adapt_power;
    wire [7:0] adapt_basis;
    wire [1:0] adapt_lambda;      // lambda dang phat (co the la ung vien dang do)
    wire [1:0] adapt_lam_best;    // lambda DA HOI TU
    wire [1:0] adapt_mode;
    wire       tx_allowed;
    wire [7:0] key_rate, stale;
    wire [23:0] adapt_slot;
    wire [7:0]  adapt_gap;

    wire [3:0] eff_power  = adaptive ? adapt_power  : man_power;
    wire [1:0] eff_lambda = adaptive ? adapt_lambda : 2'd0;

    uwoc_channel #(.COH_LOG2(12)) chan (
        .clk(clk), .rst_n(rst_n),
        .signal_in(1'b0), .signal_out(),
        .slot_width(24'd20),
        .chan_enable(1'b1),
        .water_type(water), .dist_idx(dist), .turb_level(turb),
        .lambda_sel(eff_lambda), .mu_level(eff_power),
        .p_noise(24'd218), .dynamic_enable(1'b0),
        .current_level(cur_level),
        .click(click), .no_click(no_click), .err_inject(err_inject),
        .click_count(), .lost_count(), .flip_count(),
        .h_s_out(h_s), .h_o_out(h_o), .h_f_out(h_f),
        .nexp_inv(nexp_inv),
        .sample_en(sample_en)
    );

    // ---- mo hinh chon basis (lam trong TB) ----
    reg [15:0] lfsr_b = 16'hACE1;
    always @(posedge clk)
        lfsr_b <= {lfsr_b[14:0], lfsr_b[15]^lfsr_b[13]^lfsr_b[12]^lfsr_b[10]};

    wire [7:0] basis_prob = adaptive ? adapt_basis : 8'd128;
    wire a_z = (lfsr_b[7:0]   < basis_prob);
    wire b_z = (lfsr_b[15:8]  < basis_prob);
    wire basis_match = (a_z == b_z);

    // ---- monitor ----
    wire [7:0]  qber, snr, photon, sifted, loss, jitter;
    wire [15:0] photon_cnt;
    wire        win_valid, win_pulse;

    channel_monitor #(.ATTEMPT_LOG2(AW), .NEXP_LOG2(NEXP), .MIN_SIFT(16)) mon (
        .clk(clk), .rst_n(rst_n),
        .evt_qubit_done(click),
        .evt_qubit_lost(no_click),
        .evt_basis_match(basis_match),
        .evt_data_error(err_inject & basis_match),
        .nexp_inv(nexp_inv),
        .enable(1'b1), .clear(1'b0),
        .qber(qber), .snr_level(snr),
        .photon_rate(photon), .photon_count(photon_cnt),
        .sifted_rate(sifted),
        .loss_rate(loss), .qber_jitter(jitter),
        .window_valid(win_valid), .window_pulse(win_pulse)
    );

    adaptive_controller ctrl (
        .clk(clk), .rst_n(rst_n),
        .qber(qber), .snr_level(snr), .photon_rate(photon),
        .photon_count(photon_cnt),
        .qber_jitter(jitter), .loss_rate(loss),
        .window_valid(win_valid), .window_pulse(win_pulse),
        .adaptive_enable(adaptive),
        .manual_power(man_power), .manual_basis_prob(8'd128),
        .manual_slot_width(24'd250000), .manual_lambda(2'd0),
        .power_level(adapt_power), .basis_prob_z(adapt_basis),
        .slot_width_out(adapt_slot), .rep_gap(adapt_gap),
        .lambda_sel(adapt_lambda), .lambda_best(adapt_lam_best),
        .mode(adapt_mode),
        .tx_allowed(tx_allowed), .key_rate_est(key_rate),
        .stale_windows(stale)
    );

    integer i, fails;

    // window_pulse chi cao DUNG 1 chu ky va roi vao khe giua hai lan lay mau
    // cua pulse_qubit -> phai dem bang always rieng, khong the poll trong task.
    integer win_count;
    initial win_count = 0;
    always @(posedge clk) if (win_pulse) win_count = win_count + 1;

    // Bo phat qubit chay lien tuc, doc lap voi luong dieu khien cua TB.
    initial begin
        sample_en = 1'b0;
        @(posedge rst_n);
        forever begin
            @(negedge clk); sample_en = 1'b1;
            @(negedge clk); sample_en = 1'b0;
        end
    end

    // Cho den khi da qua n_win cua so
    task run_windows;
        input integer n_win;
        integer target;
    begin
        target = win_count + n_win;
        wait (win_count >= target);
        @(negedge clk);
    end
    endtask

    task show;
        input [8*24:1] tag;
    begin
        $display("  %0s w=%0d d=%2d lv=%0d | snr=%3d qber=%3d(%.1f%%) jit=%3d clicks=%5d sift=%3d valid=%b | mode=%0d lam=%0d(best=%0d) pow=%2d stale=%0d",
                 tag, water, dist, turb, snr, qber, qber/2.0, jitter,
                 photon_cnt, sifted, win_valid, adapt_mode, adapt_lambda,
                 adapt_lam_best, adapt_power, stale);
    end
    endtask

    initial begin
        fails = 0;
        $display("");
        $display("================================================================");
        $display("  TB vong kin: uwoc_channel + channel_monitor + adaptive_controller");
        $display("  Cua so = %0d attempt (ATTEMPT_LOG2=%0d)", WIN, AW);
        $display("================================================================");

        repeat (5) @(negedge clk); rst_n = 1'b1; repeat (20) @(negedge clk);

        // ================= TEST A =================
        $display("");
        $display("[TEST A] SNR chuan hoa ~128 tai diem danh dinh (mu_level=8)");
        $display("  Muc dich: loai bo suy hao tinh exp(-c*d) khoi chi so SNR.");
        adaptive = 1'b0; man_power = 4'd8;
        begin : testA
            integer nA, okA;
            okA = 0; nA = 0;
            // clear ocean 5m / 15m / 25m ; coastal 2m / 6m ; harbor 0.5m
            for (i = 0; i < 6; i = i + 1) begin
                case (i)
                  0: begin water=2'd0; dist=4'd0; end
                  1: begin water=2'd0; dist=4'd2; end
                  2: begin water=2'd0; dist=4'd4; end
                  3: begin water=2'd1; dist=4'd0; end
                  4: begin water=2'd1; dist=4'd2; end
                  5: begin water=2'd2; dist=4'd0; end
                endcase
                turb = 3'd1;
                run_windows(3);
                show("A:");
                nA = nA + 1;
                // chap nhan 96..176 (128 +/- 25%): lay mau huu han + lam tron ROM
                if (snr >= 96 && snr <= 176) okA = okA + 1;
                else $display("     *** snr=%0d nam ngoai [96,176]", snr);
            end
            if (okA >= 5)
                $display("  [OK] %0d/%0d diem co snr trong [96,176] quanh 128", okA, nA);
            else begin
                $display("  *** FAIL: chi %0d/%0d diem dat", okA, nA);
                fails = fails + 1;
            end
        end

        // ================= TEST B =================
        $display("");
        $display("[TEST B] Cong window_valid: cu ly xa -> khong du click");
        adaptive = 1'b1;
        water = 2'd0; dist = 4'd10; turb = 3'd1;    // clear ocean 55 m: link chet
        run_windows(6);
        show("B:");
        if (!win_valid && stale > 0) begin
            $display("  [OK] window_valid=0 va stale=%0d -> controller khong hanh dong theo nhieu",
                     stale);
        end else begin
            $display("  *** FAIL: ky vong window_valid=0 o cu ly da chet link");
            fails = fails + 1;
        end
        // sau nhieu cua so im lang -> phai ve PAUSE
        run_windows(10);
        show("B2:");
        if (adapt_mode == 2'd3)
            $display("  [OK] mat link keo dai -> mode=PAUSE(3), tx_allowed=%b", tx_allowed);
        else begin
            $display("  *** FAIL: mat link nhung mode=%0d (ky vong 3)", adapt_mode);
            fails = fails + 1;
        end

        // ================= TEST C =================
        $display("");
        $display("[TEST C] Pham vi hoat dong: mode xau dan khi cu ly tang");
        adaptive = 1'b1; turb = 3'd1; water = 2'd0;
        begin : testC
            integer m0, m2, m4, m6;
            dist = 4'd0; run_windows(12); show("C:"); m0 = adapt_mode;
            dist = 4'd2; run_windows(12); show("C:"); m2 = adapt_mode;
            dist = 4'd4; run_windows(12); show("C:"); m4 = adapt_mode;
            dist = 4'd6; run_windows(12); show("C:"); m6 = adapt_mode;
            // Yeu cau CHAT: o cu ly xa (35 m, ngoai d_max ~28 m cua mo hinh)
            // controller phai chuyen HAN sang CONSERVATIVE tro len, khong duoc
            // ngoi yen o MODERATE trong khi khong bao gio du mau de ket luan.
            if (m6 > m0 && m6 >= 2)
                $display("  [OK] mode(5m)=%0d -> mode(35m)=%0d: xau dan va dat >= CONSERVATIVE",
                         m0, m6);
            else begin
                $display("  *** FAIL: mode khong xau dan dung (%0d %0d %0d %0d)",
                         m0, m2, m4, m6);
                fails = fails + 1;
            end
        end

        // ================= TEST D =================
        $display("");
        $display("[TEST D] Leo doi buoc song (0=450 blue, 1=532 green, 2=650 red)");
        $display("  Ky vong Kebapci'23 §I: clear ocean -> blue; nuoc duc -> red.");
        adaptive = 1'b1;

        water = 2'd2; dist = 4'd0; turb = 3'd1;     // harbor 0.5 m
        run_windows(60);
        show("D harbor:");
        // Kiem tra lambda_best (ket qua HOI TU), khong phai lambda_sel — trong
        // luc dang do thi lambda_sel tam thoi la lambda ung vien.
        if (adapt_lam_best == 2'd2)
            $display("  [OK] harbor hoi tu ve lam_best=2 (650 nm red)");
        else begin
            $display("  *** FAIL: harbor hoi tu ve lam_best=%0d (ky vong 2)",
                     adapt_lam_best);
            fails = fails + 1;
        end

        water = 2'd0; dist = 4'd2; turb = 3'd1;     // clear ocean 15 m
        run_windows(60);
        show("D clear:");
        if (adapt_lam_best == 2'd0)
            $display("  [OK] clear ocean hoi tu ve lam_best=0 (450 nm blue)");
        else begin
            $display("  *** FAIL: clear ocean hoi tu ve lam_best=%0d (ky vong 0)",
                     adapt_lam_best);
            fails = fails + 1;
        end

        $display("");
        $display("================================================================");
        if (fails == 0) $display("  KET QUA: TAT CA TEST DAT");
        else            $display("  KET QUA: %0d TEST HONG", fails);
        $display("================================================================");
        $display("");
        $finish;
    end

endmodule
