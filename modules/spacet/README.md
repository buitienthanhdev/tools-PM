# SpaceT — God's Eye View trong PM Tools Hub

Địa chỉ: **https://sonxit.io.vn/SpaceT**

```
Trình duyệt ─► sonxit.io.vn/SpaceT   (Flask hub :5000, static/modules/spacet/spacetModule.js)
                 └─ iframe (bản đầy đủ, tràn viền) ─► spacet.sonxit.io.vn/
                                └─ tunnel "spacet" ─► gateway.mjs :4174 ─► vite preview :4173
```

| Thành phần | Vị trí |
| --- | --- |
| Mã nguồn ứng dụng | `gods-eye-view/` (build ra `gods-eye-view/dist`) |
| Cổng public duy nhất | `gateway.mjs`: chặn `/api/setup`, `/api/realtime`, `/api/openai`, `/mcp`, `/@*`, dotfiles; chỉ cho `https://sonxit.io.vn` nhúng iframe; cache dài cho file tĩnh |
| Tunnel riêng | `cloudflared-spacet.yml` (tunnel `spacet`, tách khỏi tunnel của hub) |
| Module giao diện hub | `../../static/modules/spacet/spacetModule.js`, đăng ký trong `static/js/main.js` |
| Cấu hình app | `gods-eye-view/.env` (HOST, PORT, GEV_ALLOWED_HOSTS, GEV_EMBED_FRAME_ANCESTORS) |

`watchdog.py` tự khởi động và giám sát preview, gateway và tunnel này.

## Việt hóa (`i18n/`)

Ứng dụng tự dựng toàn bộ giao diện bằng JS và không có sẵn i18n, nên gateway chèn
`/spacet-vi.js?v=<hash>` vào mọi trang HTML (và đặt `lang="vi"`). Không sửa mã nguồn
`gods-eye-view/`, build lại vẫn giữ nguyên bản dịch.

| File | Vai trò |
| --- | --- |
| `i18n/engine.js` | Dịch text node + `title`/`aria-label`/`placeholder`/`alt` khi chúng xuất hiện trong DOM (MutationObserver) |
| `i18n/parts/*.json` | Các lô bản dịch gốc `{"English": "Tiếng Việt"}`; số được thay bằng `#` |
| `i18n/dict.vi.json` | Từ điển gộp, sinh bằng `node i18n/build-dict.mjs` (đừng sửa tay) |
| `i18n/overrides.vi.json` | Sửa tay, luôn thắng; giá trị trùng khóa = giữ tiếng Anh |

- Khớp không phân biệt hoa/thường; nguồn viết HOA thì bản dịch viết HOA.
- Chuỗi không có trong từ điển (tên địa danh, callsign, tên camera…) giữ nguyên tiếng Anh.
- Sửa một cụm từ: thêm vào `overrides.vi.json` (có hiệu lực ngay, không cần restart gateway).
- Muốn xem bản gốc: thêm `?lang=en` vào URL.
- Không dịch: logo "GOD'S EYE VIEW", tên icon Material Symbols, lệnh giọng nói (trợ lý chỉ nghe tiếng Anh).

## Chạy thủ công

```powershell
cd "D:\tools PM\modules\spacet\gods-eye-view"
npm run build                                   # sau khi sửa mã nguồn
node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4173 --strictPort
node ..\gateway.mjs                              # cửa public duy nhất, :4174
```

## Thêm API key (3D photorealistic, giọng nói, tàu biển…)

Chỉ cấu hình qua `http://localhost:4173` (POWER UP) hoặc sửa `gods-eye-view/.env`.
Qua `spacet.sonxit.io.vn` các route cài đặt/giọng nói bị gateway chặn có chủ đích:
tunnel kết nối từ chính máy này nên app thấy mọi khách là loopback.
