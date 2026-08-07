// ============================================================
// TESTBENCH — uwoc_channel.v
// ============================================================
// Cross-checks the RTL against the Python golden model (_rtl_exact_sim in uwoc_lut_gen.py).
//
// Run:
//   vlib work
//   vlog +incdir+. uwoc_channel.v tb_uwoc_channel.v
//   vsim -c -do "run -all; quit" tb_uwoc_channel
//
// TEST 1 — detection-stage statistics (§1–5 of uwoc_channel.v)
//          sweeps (water_type, dist_idx, turb_level), counting clicks / errors.
// TEST 2 — OOK signal path (§6): checks no_click → silence for the whole frame,
//          and err → flips ONLY the b0 data slot, leaving SYNC/basis untouched.
// TEST 3 — coherence time: h must stay FROZEN between two coh_ticks.
// ============================================================
`timescale 1ns / 1ps

module tb_uwoc_channel;

    // A small COH_LOG2 keeps simulation fast: fading is resampled every 256 cycles.
    // On real hardware the default of 18 is used (≈5.24 ms @50 MHz).
    localparam COH = 8;
    localparam integer N_QUBIT = 200000;

    reg clk = 1'b0, rst_n = 1'b0;
    always #10 clk = ~clk;              // 50 MHz

    reg         signal_in   = 1'b0;
    reg  [23:0] slot_width  = 24'd20;
    reg         chan_enable = 1'b1;
    reg  [1:0]  water_type  = 2'd0;
    reg  [3:0]  dist_idx    = 4'd0;
    reg  [2:0]  turb_level  = 3'd1;
    reg  [1:0]  lambda_sel  = 2'd0;     // 450 nm — khop mo hinh vang
    reg  [3:0]  mu_level    = 4'd8;
    reg  [23:0] p_noise     = 24'd218;  // Y0 = 1.30e-5 → round(1.3e-5·2^24)=218
    reg         dyn_en      = 1'b0;
    reg         sample_en   = 1'b0;

    wire        signal_out;
    wire [2:0]  cur_level;
    wire        click, no_click, err_inject;
    wire [15:0] click_cnt, lost_cnt, flip_cnt;
    wire [11:0] h_s, h_o, h_f;
    wire [15:0] nexp_inv;

    uwoc_channel #(.COH_LOG2(COH)) dut (
        .clk(clk), .rst_n(rst_n),
        .signal_in(signal_in), .signal_out(signal_out),
        .slot_width(slot_width),
        .chan_enable(chan_enable), .water_type(water_type),
        .dist_idx(dist_idx), .turb_level(turb_level),
        .lambda_sel(lambda_sel),
        .mu_level(mu_level), .p_noise(p_noise),
        .dynamic_enable(dyn_en),
        .current_level(cur_level),
        .click(click), .no_click(no_click), .err_inject(err_inject),
        .click_count(click_cnt), .lost_count(lost_cnt), .flip_count(flip_cnt),
        .h_s_out(h_s), .h_o_out(h_o), .h_f_out(h_f),
        .nexp_inv(nexp_inv),
        .sample_en(sample_en)
    );

    integer n_click, n_err, n_lost, i;
    integer fails;

    // Emit one sample_en pulse (1 cycle) and capture the result.
    // TIMING: sample_pulse fires on the posedge BETWEEN the two negedges below;
    // the click/no_click/err_inject outputs are registered, so they are valid at
    // the second negedge and cleared on the next posedge — read them EXACTLY here.
    task pulse_qubit;
    begin
        @(negedge clk); sample_en = 1'b1;
        @(negedge clk); sample_en = 1'b0;
        #1;
        if (click)      n_click = n_click + 1;
        if (no_click)   n_lost  = n_lost  + 1;
        if (err_inject) n_err   = n_err   + 1;
    end
    endtask

    // exp_p, exp_q: gia tri vang tu mo hinh float (uwoc_channel_model.py,
    // KIEM CHUNG 4). Chi kiem tra chat khi so click du lon (>500), vi o cu ly
    // xa sai lech chu yeu la nhieu ban chu khong phai loi RTL.
    task run_case;
        input [1:0] wt;
        input [3:0] di;
        input [2:0] lv;
        input real  exp_p;      // P_click ky vong
        input real  exp_q;      // QBER ky vong (phan thap phan)
        real pclick, qber, dp, dq;
    begin
        water_type = wt; dist_idx = di; turb_level = lv;
        n_click = 0; n_err = 0; n_lost = 0;
        repeat (20) @(negedge clk);
        for (i = 0; i < N_QUBIT; i = i + 1) pulse_qubit;
        pclick = n_click * 1.0 / N_QUBIT;
        qber   = (n_click > 0) ? (n_err * 1.0 / n_click) : 0.5;
        dp = (pclick - exp_p) / exp_p * 100.0; if (dp < 0) dp = -dp;
        dq = (qber - exp_q) * 100.0;           if (dq < 0) dq = -dq;
        $display("  w=%0d d=%2d lv=%0d | eff=%0d | click=%6d lost=%6d err=%5d | P=%.3e (vang %.3e, %5.1f%%) QBER=%5.2f%% (vang %5.2f%%, %4.2f%%)",
                 wt, di, lv, cur_level, n_click, n_lost, n_err,
                 pclick, exp_p, dp, qber * 100.0, exp_q * 100.0, dq);
        if (n_click + n_lost != N_QUBIT) begin
            $display("    *** FAIL: click+lost=%0d != %0d", n_click + n_lost, N_QUBIT);
            fails = fails + 1;
        end
        if (n_click > 500) begin
            if (dp > 15.0) begin
                $display("    *** FAIL: P_click lech %.1f%% so voi mo hinh vang", dp);
                fails = fails + 1;
            end
            if (dq > 2.0) begin
                $display("    *** FAIL: QBER lech %.2f%% tuyet doi so voi vang", dq);
                fails = fails + 1;
            end
        end
    end
    endtask

    // ---- TEST 2: send one OOK frame and check the output waveform ----
    integer sync_hi, b1_seen, b0_seen, k;
    reg exp_b1, exp_b0;

    task send_frame;
        input b1, b0;
    begin
        exp_b1 = b1; exp_b0 = b0;
        sync_hi = 0; b1_seen = 0; b0_seen = 0;
        // SYNC = 1
        signal_in = 1'b1;
        for (k = 0; k < slot_width; k = k + 1) begin
            @(posedge clk); #1; if (signal_out) sync_hi = sync_hi + 1;
        end
        // slot b1 (basis)
        signal_in = b1;
        for (k = 0; k < slot_width; k = k + 1) begin
            @(posedge clk); #1; if (signal_out) b1_seen = b1_seen + 1;
        end
        // slot b0 (data)
        signal_in = b0;
        for (k = 0; k < slot_width; k = k + 1) begin
            @(posedge clk); #1; if (signal_out) b0_seen = b0_seen + 1;
        end
        // IDLE
        signal_in = 1'b0;
        repeat (slot_width) @(posedge clk);
    end
    endtask

    integer prev_hs, prev_ho, changes;

    initial begin
        fails = 0;
        $display("");
        $display("================================================================");
        $display("  TESTBENCH uwoc_channel.v   (COH_LOG2=%0d, %0d qubit/case)", COH, N_QUBIT);
        $display("================================================================");

        repeat (5) @(negedge clk);
        rst_n = 1'b1;
        repeat (10) @(negedge clk);

        // ---------- TEST 1 ----------
        $display("");
        $display("[TEST 1] Thong ke tang phat hien photon");
        $display("  water: 0=clear ocean, 1=coastal, 2=harbor");
        $display("  Doi chieu voi mo hinh vang Python (uwoc_lut_gen.py --verify)");
        $display("");
        //        water dist  lv   P_click vang   QBER vang
        run_case(2'd0, 4'd0, 3'd1, 1.0391e-2, 0.0164);  // clear ocean  5 m
        run_case(2'd0, 4'd0, 3'd4, 1.0391e-2, 0.0164);
        run_case(2'd0, 4'd2, 3'd1, 3.5108e-3, 0.0268);  // clear ocean 15 m
        run_case(2'd0, 4'd2, 3'd4, 3.5108e-3, 0.0268);
        run_case(2'd0, 4'd4, 3'd1, 1.1893e-3, 0.0369);  // clear ocean 25 m
        run_case(2'd0, 4'd6, 3'd1, 2.7805e-4, 0.0584);  // clear ocean 35 m
        run_case(2'd1, 4'd0, 3'd1, 8.5280e-3, 0.0260);  // coastal      2 m
        run_case(2'd1, 4'd2, 3'd1, 1.9413e-3, 0.0437);  // coastal      6 m
        run_case(2'd1, 4'd4, 3'd1, 4.4854e-4, 0.0596);  // coastal     10 m
        run_case(2'd2, 4'd0, 3'd1, 5.1234e-3, 0.0395);  // harbor     0.5 m
        run_case(2'd2, 4'd2, 3'd1, 4.2804e-4, 0.0627);  // harbor     1.5 m

        // ---------- TEST 1b: knob buoc song ----------
        $display("");
        $display("[TEST 1b] Knob buoc song lam DOI ket qua? (0=450 1=532 2=650 nm)");
        $display("  Ky vong theo Kebapci'23 §I: clear ocean uu blue (450),");
        $display("  nuoc duc dich dan ve red (650).");
        begin : lam_test
            integer c450, c532, c650;
            // clear ocean 15 m
            water_type = 2'd0; dist_idx = 4'd2; turb_level = 3'd1;
            lambda_sel = 2'd0; n_click=0; n_err=0; n_lost=0;
            repeat(20) @(negedge clk);
            for (i=0;i<N_QUBIT;i=i+1) pulse_qubit; c450 = n_click;
            lambda_sel = 2'd1; n_click=0; n_err=0; n_lost=0;
            repeat(20) @(negedge clk);
            for (i=0;i<N_QUBIT;i=i+1) pulse_qubit; c532 = n_click;
            lambda_sel = 2'd2; n_click=0; n_err=0; n_lost=0;
            repeat(20) @(negedge clk);
            for (i=0;i<N_QUBIT;i=i+1) pulse_qubit; c650 = n_click;
            $display("  clear ocean 15m : click 450=%0d 532=%0d 650=%0d", c450, c532, c650);
            if (c450 > c532 && c532 > c650)
                $display("    [OK] blue > green > red o clear ocean");
            else begin
                $display("    *** FAIL: thu tu buoc song sai o clear ocean");
                fails = fails + 1;
            end

            // harbor 0.5 m (nuoc rat duc)
            water_type = 2'd2; dist_idx = 4'd0;
            lambda_sel = 2'd0; n_click=0; n_err=0; n_lost=0;
            repeat(20) @(negedge clk);
            for (i=0;i<N_QUBIT;i=i+1) pulse_qubit; c450 = n_click;
            lambda_sel = 2'd2; n_click=0; n_err=0; n_lost=0;
            repeat(20) @(negedge clk);
            for (i=0;i<N_QUBIT;i=i+1) pulse_qubit; c650 = n_click;
            $display("  harbor      0.5m: click 450=%0d 650=%0d", c450, c650);
            if (c650 > c450)
                $display("    [OK] red > blue o harbor (nuoc duc)");
            else begin
                $display("    *** FAIL: red khong tot hon blue o harbor");
                fails = fails + 1;
            end
        end
        lambda_sel = 2'd0;

        // ---------- TEST 2 ----------
        $display("");
        $display("[TEST 2] Duong tin hieu OOK: khung [SYNC][b1=basis][b0=data][IDLE]");

        // 2a. Ep no_click: p_sig = 0 va p_noise = 0 -> luon mat photon
        mu_level = 4'd0; p_noise = 24'd0;
        water_type = 2'd0; dist_idx = 4'd0; turb_level = 3'd1;
        repeat (20) @(negedge clk);
        pulse_qubit;
        send_frame(1'b1, 1'b1);
        if (sync_hi == 0 && b1_seen == 0 && b0_seen == 0)
            $display("  [OK] no_click -> im lang ca khung (sync=%0d b1=%0d b0=%0d)",
                     sync_hi, b1_seen, b0_seen);
        else begin
            $display("  *** FAIL: no_click nhung van co tin hieu ra (sync=%0d b1=%0d b0=%0d)",
                     sync_hi, b1_seen, b0_seen);
            fails = fails + 1;
        end

        // 2b. Ep click KHONG loi: p_sig = max, epol khong dung vi ta ep bang mu
        //     -> dung dist gan nhat + mu max de p_sig ~ 1, va kiem tra khung
        //     truyen nguyen ven khi err_inject = 0.
        mu_level = 4'd15; p_noise = 24'd0;
        water_type = 2'd0; dist_idx = 4'd0;
        repeat (20) @(negedge clk);
        // lap den khi bat duoc mot qubit click ma khong loi
        // (P_sig ~ 2e-2 o day nen can vai nghin lan thu)
        for (k = 0; k < 20000; k = k + 1) begin
            pulse_qubit;
            if (click && !err_inject) k = 100000;
        end
        if (k >= 100000) begin
            send_frame(1'b1, 1'b1);
            if (sync_hi == slot_width && b1_seen == slot_width && b0_seen == slot_width)
                $display("  [OK] click khong loi -> khung truyen nguyen ven");
            else begin
                $display("  *** FAIL: khung bi sai (sync=%0d b1=%0d b0=%0d, ky vong %0d)",
                         sync_hi, b1_seen, b0_seen, slot_width);
                fails = fails + 1;
            end
        end else
            $display("  [SKIP] khong bat duoc qubit click-khong-loi");

        // 2c. Ep click CO loi: chon cu ly xa -> epol lon; lap den khi err_inject=1
        water_type = 2'd2; dist_idx = 4'd6;   // harbor 3.5 m -> e_pol ~ 5%
        mu_level = 4'd15; p_noise = 24'h7F_FFFF;   // ep noise_det ~50% de co click
        repeat (20) @(negedge clk);
        for (k = 0; k < 5000; k = k + 1) begin
            pulse_qubit;
            if (click && err_inject) k = 100000;
        end
        if (k >= 100000) begin
            send_frame(1'b1, 1'b1);
            // SYNC va b1 phai NGUYEN VEN, chi b0 bi dao (1 -> 0)
            if (sync_hi == slot_width && b1_seen == slot_width && b0_seen == 0)
                $display("  [OK] err_inject -> CHI dao slot du lieu b0, SYNC/basis nguyen ven");
            else begin
                $display("  *** FAIL: dao sai slot (sync=%0d b1=%0d b0=%0d, ky vong %0d/%0d/0)",
                         sync_hi, b1_seen, b0_seen, slot_width, slot_width);
                fails = fails + 1;
            end
        end else
            $display("  [SKIP] khong bat duoc qubit click-co-loi");

        // ---------- TEST 3 ----------
        $display("");
        $display("[TEST 3] Thoi gian ket hop: h phai DONG BANG giua hai coh_tick");
        chan_enable = 1'b1; mu_level = 4'd8; p_noise = 24'd218;
        water_type = 2'd0; dist_idx = 4'd8; turb_level = 3'd5;
        repeat (20) @(negedge clk);
        pulse_qubit;
        prev_hs = h_s; prev_ho = h_o; changes = 0;
        // (1<<COH)/2 qubit lien tiep, moi qubit ton 3 chu ky -> van trong 1 khoi
        for (i = 0; i < (1 << COH) / 8; i = i + 1) begin
            pulse_qubit;
            if (h_s !== prev_hs || h_o !== prev_ho) changes = changes + 1;
            prev_hs = h_s; prev_ho = h_o;
        end
        if (changes <= 1)
            $display("  [OK] h_s/h_o doi %0d lan trong %0d qubit lien tiep (<=1)",
                     changes, (1 << COH) / 8);
        else begin
            $display("  *** FAIL: h doi %0d lan -> lay mau qua nhanh, sai vat ly",
                     changes);
            fails = fails + 1;
        end

        // Nhung qua nhieu khoi ket hop thi h PHAI doi
        changes = 0; prev_hs = h_s;
        for (i = 0; i < 20; i = i + 1) begin
            repeat (1 << COH) @(negedge clk);
            pulse_qubit;
            if (h_s !== prev_hs) changes = changes + 1;
            prev_hs = h_s;
        end
        if (changes >= 5)
            $display("  [OK] qua 20 khoi ket hop, h_s doi %0d lan (>=5)", changes);
        else begin
            $display("  *** FAIL: h_s chi doi %0d lan qua 20 khoi -> LFSR/ROM sai",
                     changes);
            fails = fails + 1;
        end

        // ---------- TEST 4: bypass ----------
        $display("");
        $display("[TEST 4] chan_enable = 0 -> kenh ly tuong");
        chan_enable = 1'b0;
        repeat (20) @(negedge clk);
        n_click = 0; n_lost = 0; n_err = 0;
        for (i = 0; i < 1000; i = i + 1) pulse_qubit;
        send_frame(1'b1, 1'b0);
        if (n_click == 1000 && n_lost == 0 && n_err == 0
            && sync_hi == slot_width && b1_seen == slot_width && b0_seen == 0)
            $display("  [OK] bypass: 1000/1000 click, 0 loi, khung nguyen ven");
        else begin
            $display("  *** FAIL bypass: click=%0d lost=%0d err=%0d sync=%0d b1=%0d b0=%0d",
                     n_click, n_lost, n_err, sync_hi, b1_seen, b0_seen);
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
