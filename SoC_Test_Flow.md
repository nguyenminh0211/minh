# SoC RISC-V RTL Verification Flow

## 1. Mục tiêu

Xây dựng flow kiểm thử RTL cho một SoC RISC-V gồm:

- Core RISC-V RV32I hoặc RV64I.
- Instruction cache và data cache.
- AXI/AXI4-Lite bus.
- RAM/ROM và peripheral memory-mapped.
- Random test generation.
- Reference model độc lập.
- Cocotb driver, monitor và scoreboard.
- Assertions cho protocol và invariant.
- Regression nhiều test và nhiều seed.

Mục tiêu là chạy cùng một chương trình trên reference model và RTL, sau đó so sánh trạng thái kiến trúc và các giao dịch quan trọng.

## 2. Kiến trúc tổng thể

```text
RTG / riscv-dv
        │
        ├── program.bin / ELF ──> Spike hoặc Sail
        │                           └── expected architectural state
        │
        └── program.bin / ELF ──> Cocotb
                                      │
                                      ▼
                              cocotb-vivado
                                      │
                                      ▼
                                    XSim
                                      │
                                      ▼
                              RTL SoC / DUT
                              ├── RISC-V core
                              ├── cache
                              ├── AXI bus
                              └── memory
                                      │
                                      └── actual state
                                                │
                              expected ──> scoreboard <── actual
                                                │
                                      report / waveform / coverage
```

### Quy ước

- **Mã nguồn mở có sẵn**: công cụ hoặc dự án có thể tải và sử dụng.
- **Cần xây dựng**: lớp tích hợp, cấu hình hoặc mã kiểm thử cần tự viết.

## 3. Thành phần mã nguồn mở

| Thành phần | Vai trò |
|---|---|
| [cocotb-vivado](https://github.com/themperek/cocotb-vivado) | Chạy Cocotb trên simulator XSim của Vivado |
| Vivado/XSim | Compile, elaborate và mô phỏng RTL |
| [ultraembedded/riscv](https://github.com/ultraembedded/riscv) | RTL DUT có RISC-V RV32, cache và AXI |
| [riscv-dv](https://github.com/google/riscv-dv) | Sinh chương trình/instruction ngẫu nhiên |
| [Spike](https://github.com/riscv-software-src/riscv-isa-sim) | Reference model độc lập cho RISC-V ISA |
| [Sail RISC-V](https://github.com/riscv/sail-riscv) | Reference model dựa trên đặc tả RISC-V |

## 4. Vai trò của từng thành phần

### 4.1. cocotb-vivado

`cocotb-vivado` là simulator adapter, không phải CPU model và không phải reference model.

Với RTL thuần, nó điều phối các công cụ của Vivado:

```text
xvlog / xvhdl  → compile Verilog/VHDL
xelab          → elaborate design
XSim snapshot  → chạy mô phỏng
```

Nó hỗ trợ chạy testbench Cocotb với XSim, nhưng không thực hiện synthesis, place-and-route hoặc tạo bitstream FPGA.

### 4.2. ultraembedded/riscv

`ultraembedded/riscv` nên được sử dụng làm **DUT (Design Under Test)**:

- RISC-V RV32.
- Instruction/data cache.
- AXI hoặc AXI4-Lite tùy cấu hình.
- RTL cần được kiểm thử.

Không nên dùng chính DUT làm reference model cho nó. Reference phải độc lập để tránh cùng lặp lại một lỗi.

### 4.3. Spike/Sail

Spike hoặc Sail chỉ mô tả hành vi kiến trúc:

- PC.
- Register.
- CSR.
- Instruction semantics.
- Exception/trap.
- Architectural memory state.

Chúng không mô phỏng chi tiết:

- Cache timing.
- AXI handshake.
- Pipeline timing.
- Bus arbitration.
- Clock-level behavior.
- Back-pressure.

### 4.4. riscv-dv/RTG

RTG hoặc `riscv-dv` sinh stimulus:

- Instruction sequence.
- Load/store.
- Branch/jump.
- CSR access.
- Exception/interrupt tùy cấu hình.
- Program và seed.

RTG không phải reference model. Nó chỉ tạo chương trình hoặc transaction để kiểm thử.

## 5. Các phần cần tự xây dựng

| Thành phần | Nội dung cần làm |
|---|---|
| Cocotb top-level testbench | Clock, reset, nạp firmware, start/stop, timeout |
| AXI memory model | RAM/ROM, handshake, burst, byte enable, wait-state, response |
| Reference adapter | Chạy cùng ELF/bin trên Spike/Sail và xuất expected state |
| RTL state collector | Thu PC, register, CSR, commit trace, memory write, exception |
| Scoreboard | So sánh expected state với actual state |
| AXI/cache monitor | Theo dõi transaction, hit/miss, refill, eviction |
| Assertions | Kiểm tra protocol, invariant và deadlock |
| Regression manager | Chạy nhiều seed, lưu log, waveform và kết quả |

## 6. Quy trình một test

### Bước 1: Sinh chương trình

RTG hoặc `riscv-dv` tạo:

```text
program.S
program.elf
program.bin
seed
```

Seed phải được lưu lại để có thể tái hiện test lỗi.

### Bước 2: Chạy reference model

Adapter chạy `program.elf` hoặc `program.bin` trên Spike/Sail và tạo:

```text
expected PC
expected registers
expected CSR
expected memory result
expected exception
```

Có thể lưu ở dạng JSON:

```json
{
  "pc": "0x80000020",
  "registers": {
    "x1": 10,
    "x2": 20,
    "x3": 30
  },
  "exception": null
}
```

### Bước 3: Nạp chương trình vào RTL

Cocotb nạp cùng chương trình vào AXI RAM/ROM hoặc memory model của SoC.

### Bước 4: Chạy mô phỏng RTL

Cocotb:

1. Tạo clock.
2. Kích hoạt reset.
3. Nạp memory.
4. Nhả reset.
5. Chờ `halt`, `tohost`, `done` hoặc timeout.

### Bước 5: Thu trạng thái RTL

Cần thu một hoặc nhiều loại thông tin:

- PC.
- Register file.
- CSR.
- Commit/retire trace.
- Memory write.
- Exception/trap.
- AXI transaction.
- Cache event.

XSI chủ yếu expose các port top-level. Nếu cần quan sát tín hiệu nội bộ, nên đưa tín hiệu debug ra top-level, tạo trace interface hoặc dùng monitor/assertion trong RTL.

### Bước 6: So sánh

```python
expected = run_reference(program)
actual = await run_rtl_and_collect_state(dut)

assert actual.registers == expected.registers
assert actual.memory == expected.memory
assert actual.exception == expected.exception
```

## 7. Kiểm tra AXI, cache và hệ thống

### AXI protocol

- Handshake chỉ xảy ra khi `VALID && READY`.
- Payload không đổi khi `VALID=1 && READY=0`.
- Không mất transaction.
- Không tạo response khi chưa có request.
- Một request có đúng response tương ứng.

### Bus arbitration

- Không có hai master cùng được cấp bus.
- Transaction không bị starvation ngoài giới hạn cho phép.
- Không deadlock.

### Cache

- Cache hit trả dữ liệu đúng.
- Cache miss tạo refill đúng.
- Eviction không làm mất dữ liệu.
- Dirty line được write-back đúng.
- Invalidate hoạt động đúng.
- Dữ liệu cache và memory nhất quán theo chính sách đã chọn.

### CPU và system

- Register `x0` luôn bằng 0.
- PC hợp lệ.
- Instruction retire đúng thứ tự.
- Exception gắn với đúng instruction.
- Reset đưa hệ thống về trạng thái hợp lệ.
- Không transaction treo vô hạn.

## 8. Cấu trúc thư mục đề xuất

```text
riscv-verification/
├── rtl/
│   └── ultraembedded-riscv/
├── cocotb/
│   ├── test_random.py
│   ├── clock_reset.py
│   ├── memory_model.py
│   ├── axi_monitor.py
│   ├── cache_monitor.py
│   ├── state_collector.py
│   └── scoreboard.py
├── generator/
│   ├── run_riscv_dv.py
│   └── custom_generator.py
├── reference/
│   ├── run_spike.py
│   ├── run_sail.py
│   └── trace_parser.py
├── assertions/
│   ├── axi_assertions.sv
│   ├── cache_assertions.sv
│   └── cpu_assertions.sv
├── programs/
│   ├── linker.ld
│   └── startup.S
├── regression/
│   ├── run_regression.py
│   └── seeds.txt
└── results/
    ├── logs/
    ├── waveforms/
    └── expected/
```

## 9. Lộ trình triển khai

### Giai đoạn 1: RTL smoke test

Chạy một module RTL đơn giản bằng Cocotb-vivado/XSim để xác nhận clock, reset, I/O và simulator flow.

### Giai đoạn 2: Core + memory

Kết nối RISC-V core với RAM đơn giản và chạy một chương trình cố định:

```text
load → add → store → halt
```

### Giai đoạn 3: AXI

Thêm AXI memory model, monitor, protocol assertions, wait-state và back-pressure.

### Giai đoạn 4: Reference checking

Chạy cùng program trên Spike/Sail và RTL, sau đó so sánh PC, register, memory và exception.

### Giai đoạn 5: Cache

Kiểm tra hit, miss, refill, eviction, write-back/write-through và memory consistency.

### Giai đoạn 6: Random regression

Tích hợp `riscv-dv` hoặc RTG riêng, chạy nhiều seed, random latency, random back-pressure và timeout.

### Giai đoạn 7: RV64/SoC lớn

Mở rộng sang RV64, privilege mode, MMU/TLB, interrupt, DMA, peripheral và Linux/bare-metal boot.

## 10. Kết luận

Mô hình chính xác là:

```text
cocotb-vivado     = lớp chạy Cocotb trên XSim
ultraembedded/riscv = RTL DUT cần kiểm thử
riscv-dv / RTG    = bộ sinh chương trình hoặc stimulus
Spike / Sail      = reference model độc lập cho ISA
Cocotb testbench  = driver + monitor + memory model
Scoreboard        = so sánh expected với actual
Assertions        = kiểm tra AXI, cache, bus và invariant
Regression        = chạy nhiều seed và lưu kết quả
```

Các dự án mã nguồn mở cung cấp nền tảng, nhưng lớp tích hợp vẫn phải được xây dựng: testbench Cocotb, memory model, adapter Spike/Sail, state collector, scoreboard, assertions và regression manager.
