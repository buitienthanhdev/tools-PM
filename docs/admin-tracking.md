# Dashboard quản trị và theo dõi truy cập

Trang `/admin` (chỉ admin) gồm các tab: **Tổng quan · Trực tiếp · Người dùng · Công cụ & API · Bảo mật · Lỗi · Nhật ký · Hệ thống**.
Khoảng thời gian: 1 giờ, 24 giờ, 7, 30, 90 ngày; mọi chỉ số được so với kỳ liền trước.

## Ghi lại những gì

| Nguồn | Nội dung | Không ghi |
| --- | --- | --- |
| Request API (`core/analytics.py`, after_request) | thời điểm, phương thức, đường dẫn (chuẩn hoá `:id`), tên tham số truy vấn, mã trạng thái, thời gian xử lý, dung lượng, email người dùng, IP (`CF-Connecting-IP`), quốc gia (`CF-IPCountry`), trình duyệt/HĐH/thiết bị, trang giới thiệu | thân request/response, mật khẩu, nội dung file, giá trị tham số truy vấn |
| Lượt xem trang (`static/services/tracker.js` → `/api/track/pv`) | đường dẫn SPA, tiêu đề, nguồn, độ phân giải, mã trình duyệt ngẫu nhiên (`localStorage`), thời gian ở lại (chỉ tính lúc tab hiển thị) | nội dung trang, dữ liệu nhập |
| Online | nhịp 60 giây khi tab hiển thị; hoạt động trong 5 phút = đang online (bộ nhớ, không lưu) | |
| Sự kiện | đăng nhập thành công / sai / bị chặn, đăng xuất, đăng ký, đổi mật khẩu, admin sửa / xoá tài khoản, admin xuất nhật ký | mật khẩu |
| Lỗi | máy chủ: loại, thông điệp, vị trí, traceback (4.000 ký tự cuối); trình duyệt: lỗi JS, promise bị từ chối, tài nguyên không tải được (tối đa 20/lần tải trang) | |

Không ghi: file tĩnh, tải trang SPA (đã có beacon), GET thăm dò định kỳ thành công (trạng thái task/job/health), chính các lần admin
xem dashboard. Đường dẫn của máy quét lỗ hổng (`.php`, `.env`, `wp-admin`…) vẫn được ghi dù SPA trả 200. Bot được nhận diện qua
User-Agent và tách khỏi số khách / lượt xem / yêu cầu.

## Lưu trữ và quyền riêng tư

- SQLite riêng `data/analytics/analytics.db` (đã gitignore), ghi nền theo lô — request không phải chờ ghi.
- Giữ `analytics.retention_days` ngày (mặc định 90), dọn mỗi ngày. Tắt hẳn: `"analytics": {"enabled": false}` trong `data/config.json`.
- Chỉ admin đọc được (`/api/admin/*` bị chặn với người khác). Dữ liệu gồm email và IP là **dữ liệu cá nhân** — nên thông báo
  trong điều khoản / chính sách riêng tư của trang rằng hệ thống ghi nhật ký truy cập để vận hành và bảo mật.
- Beacon `/api/track/*` công khai (cả khách chưa đăng nhập) nhưng giới hạn 120 lần/phút/IP và chỉ nhận JSON ≤ 8 KB.

## Kiểm thử

`pytest tests_hub/test_hub_analytics.py` — ghi đủ các loại, chỉ admin xem được, không lưu mật khẩu / nội dung request,
giới hạn tốc độ beacon, chuẩn hoá đường dẫn và nhận diện trình duyệt.
