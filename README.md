# Image → Excel (deepdoctection)

Pipeline chuyên xử lý **ảnh tài liệu / PDF scan**: nhận diện layout + bảng (table structure) + OCR, rồi xuất **một file Excel** giữ đúng cấu trúc bảng.

Powered by [deepdoctection](https://github.com/deepdoctection/deepdoctection).

## Tính năng

- Input: ảnh (`.png`, `.jpg`, `.tif`, …), thư mục ảnh, hoặc PDF
- Layout analysis + table segmentation + OCR (DocTR)
- Một workbook `.xlsx` gồm:
  - `Summary` / `Pages` — tổng quan
  - `Text` — nội dung chữ theo thứ tự đọc
  - `Layouts` — từng khối layout (title, text, …)
  - `T{page}_{idx}_…` — **mỗi bảng một sheet**, giữ hàng/cột
  - `TableCells` — từng ô (row/col/span) để đối chiếu độ chính xác

## Cài đặt

Python ≥ 3.10. Khuyến nghị dùng virtualenv.

```bash
python3 -m venv .venv
source .venv/bin/activate

# PyTorch (CPU). GPU: bỏ --index-url và cài bản CUDA phù hợp.
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
```

Lần chạy đầu sẽ tải model layout/OCR (cần mạng).

## Cách dùng

```bash
# Ảnh mẫu có sẵn
python convert.py samples/sample_invoice.png -o output/sample_invoice.xlsx

# Thư mục nhiều ảnh → 1 Excel
python convert.py path/to/images/ -o output/batch.xlsx

# PDF scan
python convert.py path/to/scan.pdf -o output/scan.xlsx -v
```

Tuỳ chọn cấu hình deepdoctection:

```bash
python convert.py samples/sample_invoice.png -o output/out.xlsx \
  --config USE_ROTATOR=True
```

## Cấu trúc project

```
convert.py                 # CLI tiện dụng
requirements.txt
samples/sample_invoice.png # ảnh demo
src/image_to_excel/
  converter.py             # deepdoctection → dict
  excel_writer.py          # dict → .xlsx
  __main__.py              # python -m image_to_excel
```

## Ghi chú độ chính xác

- Bảng được lấy từ `table.csv` của deepdoctection; nếu trống sẽ dựng lại từ `cells` (row/col).
- Sheet `TableCells` giúp kiểm tra OCR từng ô.
- DocTR mặc định mạnh với Latin script. Tài liệu tiếng Việt scan kém nét có thể thử Tesseract (`vie`) nếu đã cài `tesseract-ocr` + `tesseract-ocr-vie`, rồi override OCR engine qua `--config`.
