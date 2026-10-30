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
| [riscv-arch-test](https://github.com/riscv-non-isa/riscv-arch-test) | Bộ compliance test có định hướng cho ISA |
| [riscv-isac](https://github.com/riscv-software-src/riscv-isac) | Phân tích trace và đo coverage theo ISA |
| [riscv-coverage](https://github.com/riscv-non-isa/riscv-coverage) | Coverage model cho RISC-V |
| [riscv-formal](https://github.com/SymbioticEDA/riscv-formal) | Formal verification qua giao diện RVFI |
| [cocotbext-axi](https://github.com/alexforencich/cocotbext-axi) | AXI driver/monitor và bus model cho Cocotb |
| [verilog-axi](https://github.com/alexforencich/verilog-axi) | RTL AXI components, RAM, interconnect và testbench |

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

Khi chương trình được chạy trên toàn SoC, RTG không chỉ kiểm tra ALU. Các instruction
khác nhau tạo ra hoạt động ở nhiều khối:

```text
instruction fetch → I-cache → AXI read → memory
load/store        → D-cache → AXI read/write → memory
add/sub           → ALU + register file
branch/jump       → branch unit + PC update
exception/CSR     → trap and privilege logic
```

Do đó một test end-to-end của `riscv-dv` có thể đi qua core, cache, AXI và memory.
Tuy nhiên, việc một khối được đi qua không có nghĩa là mọi corner case của khối đó
đã được bao phủ.

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

### Bước 7: Kiểm tra hoạt động trung gian

Ngoài trạng thái cuối, testbench nên thu trace của:

- AXI read/write: địa chỉ, dữ liệu, burst, response và thứ tự transaction.
- I-cache/D-cache: hit, miss, refill, eviction và write-back.
- Commit/retire: PC, opcode, register write-back và trap.

Nhờ vậy có thể phân biệt lỗi architectural của core với lỗi ở cache, AXI hoặc memory.

## 7. Nạp chương trình và đường đi thực tế

Có hai giai đoạn khác nhau:

```text
Giai đoạn chuẩn bị:
    Cocotb → ghi trực tiếp AXI RAM/memory model → program đã nằm trong memory

Giai đoạn thực thi:
    Core → I-cache/D-cache → AXI → memory
```

Việc Cocotb ghi trực tiếp vào memory lúc khởi tạo thường bypass cache vì CPU chưa
chạy. Điều đó không làm mất kiểm tra cache: khi CPU fetch instruction hoặc thực hiện
load/store, các request vẫn đi qua cache và AXI. Nếu cần kiểm tra boot loader hoặc DMA,
hãy tạo test để dữ liệu được nạp bởi một AXI master thực tế thay vì ghi trực tiếp.

## 8. Kiểm tra AXI, cache và hệ thống

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

## 9. Random hóa môi trường SoC

`riscv-dv` random hóa chủ yếu instruction và memory access pattern. Cocotb và memory
model phải random hóa điều kiện môi trường để stress các khối khác:

- Độ trễ memory.
- AXI `READY` delay và back-pressure.
- Độ trễ hoặc thứ tự response hợp lệ.
- Burst length và byte enable.
- Error response.
- Thời điểm interrupt.
- Reset trong hoặc gần một transaction.

Ví dụ cùng một program có thể chạy nhiều lần với các seed môi trường khác nhau:

```text
program seed = 100
AXI latency seed = 1  → run A
AXI latency seed = 2  → run B
AXI latency seed = 3  → run C
```

Mỗi lần chạy phải lưu cả instruction seed và environment seed để tái hiện lỗi.

## 10. Directed tests cho corner case

Random instruction testing là xương sống của flow, nhưng không đủ để đảm bảo các trạng
thái hiếm. Nên có các nhóm test định hướng:

| Nhóm | Ví dụ |
|---|---|
| Core/ISA | Branch taken/not-taken, CSR, illegal instruction, exception |
| I-cache | Sequential fetch, jump xa, conflict address, refill |
| D-cache | Hit, miss, dirty eviction, write-back, invalidate |
| AXI | Burst, wait-state, back-pressure kéo dài, response lỗi |
| Memory | Byte enable, boundary, alignment, vùng địa chỉ lỗi |
| Arbitration | Hai master cùng request, fairness, starvation |
| System | Interrupt trong lúc stall, DMA/cache interaction, reset giữa transaction |

Các test này có thể là assembly/C cố định hoặc generator có constraint. Không cần một
file duy nhất; nên chia thành nhiều test dùng chung infrastructure của Cocotb.

Ví dụ ép cache conflict:

```asm
store x1, 0x0000(x0)
store x2, 0x1000(x0)
load  x3, 0x0000(x0)
```

Sau đó scoreboard kiểm tra kết quả dữ liệu, còn cache monitor kiểm tra miss/refill/eviction.

## 11. Các lớp kiểm thử

### End-to-end random

```text
riscv-dv → program → toàn bộ SoC → Spike/Sail scoreboard
```

Kiểm tra hành vi kiến trúc và các hoạt động phát sinh tự nhiên của core, cache, AXI
và memory.

### Monitor/scoreboard trung gian

Trong cùng test end-to-end, monitor kiểm tra transaction và event ở giữa đường đi:
AXI ordering, response, cache event, memory write và commit trace.

### Directed component tests

Ép các corner case mà random program khó tạo ra, đặc biệt cho cache, AXI, arbitration,
interrupt, reset và peripheral.

### Formal checks

`riscv-formal` bổ sung kiểm tra từng instruction và invariant qua RVFI. Formal không
thay thế random simulation, nhưng bắt được nhiều trường hợp mà random khó gặp.

## 12. Cấu trúc thư mục đề xuất

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
├── directed/
│   ├── core/
│   ├── cache/
│   ├── axi/
│   ├── memory/
│   └── soc/
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

## 12.1. Bộ công cụ bổ trợ cho `riscv-dv`

| Mục tiêu | Công cụ nên dùng |
|---|---|
| Random instruction/program | `riscv-dv` hoặc RTG riêng |
| ISA reference | Spike; Sail để cross-check khi cần |
| ISA compliance | `riscv-arch-test` |
| Trace/ISA coverage | `riscv-isac` hoặc `riscv-coverage` |
| AXI Cocotb driver/monitor | `cocotbext-axi` |
| AXI RTL component/reference | `verilog-axi` |
| Instruction/invariant formal | `riscv-formal` |
| RTL simulator | `cocotb-vivado` + Vivado XSim |

Stack khuyến nghị:

```text
ultraembedded/riscv          = RTL DUT
cocotb-vivado + XSim         = simulator
riscv-dv                    = random program
Spike/Sail                   = architectural reference
riscv-arch-test              = directed ISA compliance
cocotbext-axi                = AXI driver/monitor
verilog-axi                  = AXI RTL components
riscv-isac/riscv-coverage    = coverage
riscv-formal                 = formal checks
```

## 13. Lộ trình triển khai

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

Tích hợp `riscv-dv` hoặc RTG riêng, chạy nhiều instruction seed và environment seed,
random latency, random back-pressure, AXI monitor, cache monitor, timeout và coverage.

### Giai đoạn 6.1: Directed corner cases

Thêm các test định hướng cho cache conflict/eviction, dirty write-back, AXI burst,
back-pressure, error response, unaligned/boundary access, interrupt, DMA và reset.

### Giai đoạn 6.2: Coverage và formal

Đo ISA/functional coverage bằng `riscv-isac` hoặc `riscv-coverage`, chạy `riscv-arch-test`
cho compliance và thêm `riscv-formal` cho instruction/invariant checking.

### Giai đoạn 7: RV64/SoC lớn

Mở rộng sang RV64, privilege mode, MMU/TLB, interrupt, DMA, peripheral và Linux/bare-metal boot.

## 14. Kết luận

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

`riscv-dv` có thể dùng để kiểm thử end-to-end toàn SoC, nhưng không tự bao phủ mọi
corner case của cache, AXI, memory và peripheral. Flow hoàn chỉnh cần kết hợp:

```text
riscv-dv/RTG
    + Spike/Sail
    + Cocotb-vivado/XSim
    + random AXI/memory environment
    + AXI/cache monitors
    + assertions
    + directed corner-case tests
    + coverage
    + formal verification
```

Nói ngắn gọn:

> RTG tạo hoạt động của CPU; Cocotb tạo điều kiện môi trường; monitor và assertion
> kiểm tra đường đi; Spike/Sail kiểm tra kết quả kiến trúc; directed tests ép corner
> case; coverage và formal giúp đánh giá mức độ đầy đủ của verification.
