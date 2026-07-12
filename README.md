# SearXNG on Vercel (Experimental)

Project thử nghiệm để chạy **SearXNG trực tiếp trong Vercel Python Function** dưới dạng ứng dụng WSGI stateless.

> Đây không phải mô hình triển khai chính thức được SearXNG khuyến nghị. Không nên dùng làm public instance có lưu lượng lớn. Một số search engine có thể chặn IP datacenter của Vercel, cold start có thể chậm và function không có state dùng chung.

## Kiến trúc

```text
Client
  -> Vercel rewrite /(.*)
  -> api/index.py
  -> api/runtime.py
  -> searx.webapp.app
  -> các search engine bên ngoài
```

Các điểm chính:

- `api/index.py` export biến WSGI `app` để Vercel nhận diện.
- `config/settings.yml` kế thừa cấu hình mặc định của SearXNG và áp dụng override phù hợp với serverless.
- Không dùng Valkey/Redis, shared limiter hoặc persistent filesystem.
- Hỗ trợ kết quả `html` và `json`.
- SearXNG được pin tại commit `c19d86faa`.
- `vendor/searxng_source` là PEP 517 build-wrapper. Wrapper tải source archive đúng commit rồi delegate quá trình build wheel cho upstream `setuptools` backend. Cách này tránh phụ thuộc vào việc tùy biến install command của Vercel.

## Deploy lên Vercel

### 1. Tạo repository

Giải nén project, push toàn bộ source lên GitHub, GitLab hoặc Bitbucket.

### 2. Import vào Vercel

Trong Vercel Dashboard:

1. Chọn **Add New → Project**.
2. Import repository vừa tạo.
3. Để **Framework Preset** là `Other`.
4. Không cấu hình Build Command hoặc Output Directory riêng.

### 3. Thêm biến môi trường

Tạo secret tối thiểu 32 ký tự:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Thêm vào **Project Settings → Environment Variables**:

```text
SEARXNG_SECRET=<giá trị vừa tạo>
```

Áp dụng biến này cho `Production`, `Preview` và `Development` nếu cần dùng cả ba môi trường.

### 4. Deploy

Bấm **Deploy**. Trong build log, Vercel sẽ:

1. Đọc `requirements.txt`.
2. Build local package `vendor/searxng_source`.
3. Wrapper tải SearXNG tại commit đã pin.
4. Build và cài wheel cùng dependencies.
5. Bundle Python Function với `config/settings.yml`.

## Kiểm tra sau deploy

Health check:

```text
https://<project>.vercel.app/healthz
```

Kết quả mong đợi:

```json
{
  "service": "searxng-vercel",
  "status": "ok"
}
```

Tìm kiếm bằng giao diện:

```text
https://<project>.vercel.app/search?q=vercel
```

Tìm kiếm JSON:

```text
https://<project>.vercel.app/search?q=vercel&format=json
```

## Chạy local

Yêu cầu:

- Python 3.13
- Git không bắt buộc vì build-wrapper tải source archive qua HTTPS
- Internet để tải SearXNG và dependencies

Linux/macOS:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export SEARXNG_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python -m flask --app api.index run --host 127.0.0.1 --port 8888
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:SEARXNG_SECRET = python -c "import secrets; print(secrets.token_hex(32))"
python -m flask --app api.index run --host 127.0.0.1 --port 8888
```

Mở `http://127.0.0.1:8888`.

## Kiểm tra source project

Cài dependency test nếu môi trường chưa có `pytest` và `PyYAML`, sau đó chạy:

```bash
python -m pytest -q
python scripts/verify.py
python -m compileall -q api scripts vendor
```

`verify.py` kiểm tra:

- Các file bắt buộc.
- Python 3.13.
- Commit SearXNG đã pin.
- PEP 517 local build-wrapper.
- Cấu hình stateless/safe cho serverless.
- Rewrite, `maxDuration` và `includeFiles` của Vercel.
- Cú pháp Python, YAML và JSON.

## Cấu hình

### Bắt buộc

| Biến | Ý nghĩa |
|---|---|
| `SEARXNG_SECRET` | Secret key của Flask/SearXNG, tối thiểu 32 ký tự. |

### Tùy chọn

| Biến | Ý nghĩa |
|---|---|
| `SEARXNG_SETTINGS_PATH` | Ghi đè đường dẫn settings. Mặc định là `config/settings.yml`. |
| `SEARXNG_BASE_URL` | Base URL công khai khi cần ghi đè URL tự nhận diện. |

Runtime luôn ép các giá trị sau để giữ deployment stateless:

```text
SEARXNG_LIMITER=false
SEARXNG_IMAGE_PROXY=false
SEARXNG_PUBLIC_INSTANCE=false
SEARXNG_METHOD=GET
```

## Giới hạn đã biết

- Không có Valkey/Redis và không có shared state giữa các function instance.
- Limiter bị tắt; hãy dùng Vercel Firewall hoặc đặt deployment sau authentication nếu đưa ra Internet.
- Cấu hình engine suspension/cache chỉ tồn tại trong vòng đời của từng function instance.
- IP egress của Vercel có thể bị một số search engine rate-limit hoặc chặn.
- Cold start phải import SearXNG và khởi tạo nhiều engine.
- Request có thể dừng khi vượt giới hạn thời gian của Vercel.
- Image proxy bị tắt để giảm bandwidth và thời gian thực thi.
- Không có retry riêng ở wrapper HTTP runtime; lỗi engine được SearXNG xử lý theo cơ chế upstream.

## Troubleshooting

### Build lỗi khi tải source

Kiểm tra build log có truy cập được:

```text
https://codeload.github.com/searxng/searxng/tar.gz/c19d86faa
```

Nếu mạng build chặn GitHub, deploy sẽ không thể dựng dependency SearXNG.

### `SEARXNG_SECRET is required`

Thêm `SEARXNG_SECRET` trong Vercel Project Settings và redeploy. Thay đổi environment variable không áp dụng ngược cho deployment cũ.

### `/healthz` trả về 500

Mở Vercel Function Logs và kiểm tra:

- Secret có đủ 32 ký tự hay không.
- `config/settings.yml` có nằm trong function bundle hay không.
- SearXNG wheel đã build thành công hay chưa.

### UI chạy nhưng không có kết quả

Thường do engine timeout, CAPTCHA, rate-limit hoặc IP datacenter bị chặn. Kiểm tra logs và giảm số engine được bật trong `config/settings.yml` nếu cần.

## Nâng cấp SearXNG

1. Chọn một commit upstream đã kiểm tra.
2. Đổi `UPSTREAM_REF` trong `vendor/searxng_source/build_backend.py`.
3. Đổi `PINNED_COMMIT` trong `scripts/verify.py`.
4. Cập nhật test pin tương ứng.
5. Chạy toàn bộ verification trước khi deploy.

Không nên đổi sang branch `master`, vì build sau có thể nhận source khác mà không có thay đổi trong repository này.

## License

SearXNG được phát hành theo **GNU Affero General Public License v3.0 or later**. Xem `LICENSE-NOTICE.md` trước khi công khai deployment hoặc phân phối bản đã sửa đổi.
