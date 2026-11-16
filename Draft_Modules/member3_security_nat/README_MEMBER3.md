# THÀNH VIÊN 3: HƯỚNG DẪN LÀM BÀI MẢNG SECURITY, NAT & NETWORK AUTOMATION (STEP 7 & STEP 9)

- **Nhánh Git làm việc:** `feature/security-automation`
- **Thư mục soạn thảo CLI:** `Draft_Modules/member3_security_nat/member3_security_nat_draft.cfg`
- **Thư mục code Automation:** `Automation/inventory.yaml` và `Automation/auto_provision.py`
- **Tài liệu tham chiếu bắt buộc:** [`Specs/IP_Addressing_Schema.md`](../../Specs/IP_Addressing_Schema.md)

> **Lưu ý Zero-Conflict:** Không lưu mật khẩu dạng chữ rõ (plaintext password) trong file Python hoặc YAML. Tuân thủ đúng IP quản trị VLAN 99 và quy hoạch subnet trong `Specs/IP_Addressing_Schema.md`.

---

## Danh sách công việc cần hoàn thành (Checklist theo Rubric & Pre-Submission Checklist)

### 1. Step 7: Security, NAT/PAT & Device Hardening
- [ ] **PAT / NAT Overload trên 3 Router biên (`HCMC-EDGE-RTR01`, `HANOI-RND-RTR01`, `DANANG-LOG-RTR01`):**
  - Gắn `ip nat outside` trên cổng WAN `Gi0/0`; gắn `ip nat inside` trên các cổng/sub-interface hướng về mạng nội bộ (lưu ý **KHÔNG NAT** lưu lượng đi qua IPsec VPN Tunnel giữa 3 chi nhánh bằng ACL loại trừ `deny` trước `permit`).
  - Cấu hình `ip nat inside source list ACL_NAT_INTERNET interface GigabitEthernet0/0 overload`.
- [ ] **Extended ACL Cách ly Mạng Khách & Bảo vệ Phân vùng Nhạy cảm:**
  - Tại **Hà Nội (`HANOI-RND-RTR01`)**: Gắn ACL vào `Gi0/1.50` (`VLAN 50 - GUEST_WIFI`: `10.20.50.0/25`):
    - **Chặn (`deny ip`)** truy cập vào tất cả mạng nội bộ TVI (`10.10.0.0/16`, `10.20.0.0/16`, `10.30.0.0/16`, `192.168.0.0/16`).
    - **Cho phép (`permit`)** truy cập DHCP/DNS cần thiết (nếu cấp từ server) và đi Internet (`8.8.8.8` / `any`).
  - Tại **HQ & Đà Nẵng**: Viết ACL bảo vệ phân vùng `EXEC_FINANCE` (`10.10.10.0/24`) và `LOGISTICS_OPS` (`10.30.30.0/24`).
- [ ] **Layer 2 Security (Port Security, DHCP Snooping, DAI) trên các Switch Access:**
  - `switchport port-security` (giới hạn `maximum 2`, `mac-address sticky`, `violation restrict`).
  - `ip dhcp snooping` + `ip dhcp snooping vlan 10,20,30,50` + `ip dhcp snooping trust` trên các cổng Trunk uplink.
  - `ip arp inspection vlan 10,20,30,50` + `ip arp inspection trust` trên các cổng Trunk uplink.
- [ ] **Device Hardening & SSHv2 trên toàn bộ 10 thiết bị (theo Trang 18 & 20 Đề bài):**
  - `ip domain name tvi.lab`
  - `crypto key generate rsa modulus 2048`
  - `ip ssh version 2`
  - `username admin privilege 15 secret Cisco123!`
  - `line vty 0 4` $\rightarrow$ `transport input ssh`, `login local` (vô hiệu hóa hoàn toàn Telnet, `no ip http server`, ưu tiên HTTPS/SNMPv3).

### 2. Step 9: Network Automation (`Automation/inventory.yaml` & `Automation/auto_provision.py`)
- [ ] **`Automation/inventory.yaml`:** Khai báo danh sách thiết bị chuẩn xác (`HCMC-CORE-SW01`: `192.168.1.10`, `HANOI-RND-SW01`: `192.168.2.10`, `DANANG-LOG-SW01`: `192.168.3.10`, `device_type: cisco_ios`, port SSH `22`).
- [ ] **`Automation/auto_provision.py` (Python Netmiko + PyYAML):**
  - Yêu cầu nhập username/password qua `input()` và `getpass()` (tuyệt đối không hardcode mật khẩu).
  - Chụp trạng thái `show running-config` và `show ip interface brief` trước & sau khi cấu hình, lưu ra `Automation/backups/<hostname>_<timestamp>_backup.cfg`.
  - Đẩy cấu hình chuẩn gồm `ntp server 10.10.10.50`, `banner motd`, và các VLAN chuẩn (`10: EXEC_FINANCE`, `20: RND_ENGINEERING`, `30: LOGISTICS_OPS`, `99: MANAGEMENT`).
  - Bắt lỗi đầy đủ bằng `try/except` (`NetmikoTimeoutException`, `NetmikoAuthenticationException`, `Exception`) để không crash khi có node chết, và ghi log chi tiết vào `Automation/logs/automation.log`.

---

## Cách nộp bài khi hoàn thành
```bash
git add Draft_Modules/member3_security_nat/ Automation/
git commit -m "feat(security-automation): complete Step 7 security/NAT & Step 9 Netmiko script"
git push origin HEAD
```
