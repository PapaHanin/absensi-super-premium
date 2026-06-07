import streamlit as st
import pandas as pd
import sqlite3
import datetime
import plotly.express as px
import urllib.parse
import hashlib
import io

# ==========================================
# CONFIGURATION & DATABASE INITIALIZATION
# ==========================================
st.set_page_config(page_title="Sistem Absensi Digital Terpadu (SUPER PREMIUM)", layout="wide", page_icon="💎")

DB_FILE = "absensi_sekolah_premium.db"

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY, 
                    password TEXT, 
                    role TEXT, 
                    nama TEXT,
                    kelas_tugas TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS siswa (
                    nisn TEXT PRIMARY KEY, nama TEXT, kelas TEXT, nis TEXT, 
                    tempat_lahir TEXT, tanggal_lahir TEXT, agama TEXT, nik TEXT, 
                    alamat TEXT, nama_ayah TEXT, pekerjaan_ayah TEXT, nama_ibu TEXT, 
                    pekerjaan_ibu TEXT, no_wa_orang_tua TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS absensi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nisn TEXT, tanggal TEXT, status TEXT, waktu TEXT, guru_input TEXT,
                    mapel TEXT DEFAULT 'Wali Kelas / Umum',
                    jam_ke TEXT DEFAULT 'Harian',
                    FOREIGN KEY(nisn) REFERENCES siswa(nisn),
                    UNIQUE(nisn, tanggal, mapel, jam_ke))''')
        
    c.execute('''CREATE TABLE IF NOT EXISTS laporan_tindak_lanjut (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nisn TEXT, tanggal TEXT, catatan TEXT, status_wa TEXT,
                    FOREIGN KEY(nisn) REFERENCES siswa(nisn))''')
                    
    c.execute('''CREATE TABLE IF NOT EXISTS aduan_curhat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tanggal TEXT,
                    guru_pengirim TEXT,
                    jenis_aduan TEXT,
                    isi_curhat TEXT,
                    status_tindak_lanjut TEXT DEFAULT 'Belum Dibaca',
                    catatan_kepsek TEXT DEFAULT '-')''')
    
    try:
        c.execute("ALTER TABLE absensi ADD COLUMN mapel TEXT DEFAULT 'Wali Kelas / Umum'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE absensi ADD COLUMN jam_ke TEXT DEFAULT 'Harian'")
    except sqlite3.OperationalError:
        pass
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_admin = hash_password("admin123")
        c.execute("INSERT INTO users VALUES ('admin', ?, 'Admin', 'Kepala Sekolah', 'SEMUA')", (hashed_admin,))
    
    conn.commit()
    conn.close()

init_db()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.nama = ""
    st.session_state.kelas_tugas = ""

def get_db_connection():
    return sqlite3.connect(DB_FILE)

def kirim_wa_link(no_wa, nama_siswa, kelas, status, konteks_absen="Hari ini"):
    clean_wa = ''.join(filter(str.isdigit, str(no_wa)))
    if clean_wa.startswith('0'):
        clean_wa = '62' + clean_wa[1:]
    
    pesan = f"Assalamualaikum Wr. Wb. Bapak/Ibu Wali Murid, kami menginfokan bahwa *{nama_siswa}* Kelas *{kelas}* *TIDAK HADIR* tanpa keterangan pada {konteks_absen}. Mohon segera hubungi pihak sekolah untuk konfirmasi. Terima kasih."
    pesan_encoded = urllib.parse.quote(pesan)
    return f"https://wa.me/{clean_wa}?text={pesan_encoded}"

# ==========================================
# HALAMAN LOGIN SYSTEM
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #4F46E5;'>💎 LOGIN ABSENSI DIGITAL PREMIUM</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username / NIP")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Masuk Ke Sistem Premium", use_container_width=True)
            
            if submitted:
                hashed_input = hash_password(password)
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT role, nama, kelas_tugas FROM users WHERE username=? AND (password=? OR password=?)", (username, password, hashed_input))
                user = c.fetchone()
                conn.close()
                
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = user[0]
                    st.session_state.nama = user[1]
                    st.session_state.kelas_tugas = user[2] if user[2] else "Belum Diatur"
                    st.rerun()
                else:
                    st.error("Username atau Password keliru. Silakan hubungi operator.")
    st.stop()

# ==========================================
# SIDEBAR LOGOUT & INFO
# ==========================================
st.sidebar.markdown(f"**Pengguna:** {st.session_state.nama} ({st.session_state.role})")
if st.session_state.role == "Guru":
    st.sidebar.info(f"📍 **Hak Akses:** Kelas {st.session_state.kelas_tugas}")
if st.sidebar.button("Keluar dari Aplikasi", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()

# ==========================================
# INTERFACE: DASHBOARD ADMIN (KEPALA SEKOLAH)
# ==========================================
if st.session_state.role == "Admin":
    st.title("🏛️ Panel Utama Kepala Sekolah (Premium Admin)")
    
    tgl_pantau = st.date_input("Pilih Tanggal Pantauan Laporan", datetime.date.today())
    
    conn = get_db_connection()
    total_siswa = conn.execute("SELECT COUNT(*) FROM siswa").fetchone()[0]
    total_hadir = conn.execute("SELECT COUNT(*) FROM absensi WHERE tanggal=? AND status='hadir' AND jam_ke='Harian'", (str(tgl_pantau),)).fetchone()[0]
    total_sakit = conn.execute("SELECT COUNT(*) FROM absensi WHERE tanggal=? AND status='sakit' AND jam_ke='Harian'", (str(tgl_pantau),)).fetchone()[0]
    total_alpa = conn.execute("SELECT COUNT(*) FROM absensi WHERE tanggal=? AND status='tidak_hadir' AND jam_ke='Harian'", (str(tgl_pantau),)).fetchone()[0]
    conn.close()
    
    persen_hadir = (total_hadir / total_siswa * 100) if total_siswa > 0 else 0
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric(label="Total Siswa Terdaftar", value=f"{total_siswa} Anak")
    with col_m2:
        st.metric(label="Persentase Kehadiran Pagi (Harian)", value=f"{persen_hadir:.1f}%")
    with col_m3:
        st.metric(label="Siswa Sakit / Izin Harian", value=f"{total_sakit} Anak")
    with col_m4:
        st.metric(label="Siswa Alpa Harian", value=f"{total_alpa} Anak")
        
    st.write("---")
    
    tabs = st.tabs(["📊 Grafik Analisis Makro", "📥 Kotak Aduan & Curhat Guru", "🚨 Rekap Siswa Bermasalah", "🔄 Kenaikan Kelas Massal", "📝 Laporan Tindak Lanjut Guru", "📑 Cetak Laporan Bulanan", "👥 Manajemen Akun Guru"])
    
    with tabs[0]:
        st.subheader("Analisis Grafik Kehadiran Siswa (Umum/Harian)")
        conn = get_db_connection()
        df_absensi = pd.read_sql_query('''
            SELECT s.kelas, a.status, COUNT(a.id) as jumlah 
            FROM siswa s 
            LEFT JOIN absensi a ON s.nisn = a.nisn AND a.tanggal = ? AND a.jam_ke = 'Harian'
            GROUP BY s.kelas, a.status
        ''', conn, params=(str(tgl_pantau),))
        conn.close()
        df_absensi['status'] = df_absensi['status'].fillna('Belum Absen')
        if not df_absensi.empty:
            fig = px.bar(df_absensi, x='kelas', y='jumlah', color='status', 
                         title=f"Grafik Kehadiran Per Kelas Tanggal {tgl_pantau}",
                         barmode='group', color_discrete_map={'hadir':'#22C55E','sakit':'#FBBF24','tidak_hadir':'#EF4444','Belum Absen':'#9CA3AF'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada transaksi absensi masuk pada tanggal terpilih.")

    with tabs[1]:
        st.subheader("📥 Kotak Masuk Aduan, Saran, & Curcuran Hati Guru")
        st.info("Halaman ini hanya bisa diakses oleh Kepala Sekolah. Semua masukan bersifat rahasia untuk menjaga keterbukaan komunikasi sekolah.")
        
        conn = get_db_connection()
        df_aduan_admin = pd.read_sql_query("SELECT id, tanggal, guru_pengirim as [Dari Guru], jenis_aduan as [Kategori], isi_curhat as [Isi Pesan/Aduan], status_tindak_lanjut as [Status], catatan_kepsek as [Catatan Kepsek] FROM aduan_curhat ORDER BY id DESC", conn)
        conn.close()
        
        if df_aduan_admin.empty:
            st.info("Belum ada aduan atau saran yang masuk dari guru-guru.")
        else:
            for idx, r_aduan in df_aduan_admin.iterrows():
                with st.expander(f"✉️ [{r_aduan['Kategori']}] Dari: {r_aduan['Dari Guru']} | Tanggal: {r_aduan['tanggal']} ({r_aduan['Status']})"):
                    st.markdown(f"**Isi Curhat/Komplain:**\n> {r_aduan['Isi Pesan/Aduan']}")
                    st.write(f"**Tanggapan/Catatan Saat Ini:** {r_aduan['Catatan Kepsek']}")
                    
                    with st.form(f"tanggapi_aduan_{r_aduan['id']}"):
                        isi_tanggapan = st.text_area("Tulis Tanggapan / Tindak Lanjut Kepala Sekolah:", value=r_aduan['Catatan Kepsek'] if r_aduan['Catatan Kepsek'] != '-' else "")
                        status_baru = st.selectbox("Ubah Status Laporan:", ["Belum Dibaca", "Sedang Ditinjau", "Sudah Ditindaklanjuti"], index=["Belum Dibaca", "Sedang Ditinjau", "Sudah Ditindaklanjuti"].index(r_aduan['Status']))
                        
                        if st.form_submit_button("💾 Simpan Tanggapan Kepsek"):
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute("UPDATE aduan_curhat SET status_tindak_lanjut=?, catatan_kepsek=? WHERE id=?", (status_baru, isi_tanggapan if isi_tanggapan else '-', r_aduan['id']))
                            conn.commit()
                            conn.close()
                            st.success("Tanggapan berhasil disimpan!")
                            st.rerun()

    with tabs[2]:
        st.subheader("🚨 Daftar Kronis Siswa Bermasalah (Sering Alpa)")
        st.write("Sistem menyaring otomatis siswa yang memiliki akumulasi Alpa terbanyak di sekolah untuk tindakan preventif.")
        
        conn = get_db_connection()
        df_kronis_admin = pd.read_sql_query('''
            SELECT s.kelas as [Kelas], s.nisn as [NISN], s.nama as [Nama Siswa], s.no_wa_orang_tua as [WA Orang Tua],
                   COUNT(a.id) as [Total Alpa Terakumulasi]
            FROM siswa s
            JOIN absensi a ON s.nisn = a.nisn
            WHERE LOWER(a.status) = 'tidak_hadir'
            GROUP BY s.nisn
            HAVING [Total Alpa Terakumulasi] >= 1
            ORDER BY [Total Alpa Terakumulasi] DESC
        ''', conn)
        conn.close()
        
        if df_kronis_admin.empty:
            st.success("Luar biasa! Belum ada siswa yang tercatat Alpa di sekolah ini.")
        else:
            st.dataframe(df_kronis_admin, use_container_width=True)

    with tabs[3]:
        st.subheader("🔄 Fitur Kenaikan & Perpindahan Kelas Massal (Tahun Ajaran Baru)")
        conn = get_db_connection()
        list_kelas_asal = [r[0] for r in conn.execute("SELECT DISTINCT kelas FROM siswa WHERE kelas != ''").fetchall()]
        conn.close()
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            kelas_asal = st.selectbox("Pilih Kelas Asal (Saat Ini):", list_kelas_asal, key="asal_massal")
        with col_up2:
            kelas_tujuan = st.text_input("Ketik Kelas Tujuan Baru (Misal: 7B, 8A, LULUS):").strip().upper()
        check_konfirmasi_naik = st.checkbox(f"Saya setuju memindahkan massal semua siswa kelas {kelas_asal} menuju kelas {kelas_tujuan}")
        if st.button("🚀 Proses Pindah Kelas Massal", type="primary"):
            if kelas_tujuan == "": st.error("Kelas tujuan baru wajib diisi!")
            elif not check_konfirmasi_naik: st.error("Wajib centang kotak konfirmasi persetujuan!")
            else:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("UPDATE siswa SET kelas = ? WHERE kelas = ?", (kelas_tujuan, kelas_asal))
                jumlah_terubah = c.rowcount
                conn.commit()
                conn.close()
                st.success(f"Sukses! Sebanyak {jumlah_terubah} siswa dari kelas {kelas_asal} dipindahkan ke kelas {kelas_tujuan}.")
                st.rerun()

    with tabs[4]:
        st.subheader("Pantauan Laporan Khusus Siswa Bermasalah (Alpa)")
        conn = get_db_connection()
        df_laporan = pd.read_sql_query('''
            SELECT l.tanggal, s.kelas, s.nama, l.catatan, l.status_wa 
            FROM laporan_tindak_lanjut l
            JOIN siswa s ON l.nisn = s.nisn
            ORDER BY l.id DESC
        ''', conn)
        conn.close()
        st.dataframe(df_laporan, use_container_width=True)

    with tabs[5]:
        st.subheader("Ekspor Laporan Rekapitulasi Bulanan (Umum)")
        col_bln, col_thn = st.columns(2)
        with col_bln: bulan_pilih = st.selectbox("Pilih Bulan", [f"{i:02d}" for i in range(1, 13)], index=datetime.date.today().month - 1, key="bln_admin")
        with col_thn: tahun_pilih = st.selectbox("Pilih Tahun", [str(datetime.date.today().year), str(datetime.date.today().year - 1)], key="thn_admin")
        filter_periode = f"{tahun_pilih}-{bulan_pilih}-%"
        if st.button("Generate Rekap Bulanan Excel", type="primary"):
            conn = get_db_connection()
            df_rekap = pd.read_sql_query('''
                SELECT s.kelas, s.nisn, s.nama,
                       SUM(CASE WHEN LOWER(a.status) = 'hadir' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as Total_Hadir,
                       SUM(CASE WHEN LOWER(a.status) = 'sakit' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as Total_Sakit,
                       SUM(CASE WHEN LOWER(a.status) = 'tidak_hadir' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as Total_Alpa
                FROM siswa s
                LEFT JOIN absensi a ON s.nisn = a.nisn AND a.tanggal LIKE ?
                GROUP BY s.nisn
                ORDER BY s.kelas, s.nama
            ''', conn, params=(filter_periode,))
            conn.close()
            if not df_rekap.empty:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_rekap.to_excel(writer, sheet_name='Rekap Bulanan', index=False)
                st.success("File Excel Berhasil Dibuat!")
                st.download_button(label="📥 Unduh File Rekap Absensi (.xlsx)", data=buffer.getvalue(), file_name=f"Rekap_Absensi_{bulan_pilih}_{tahun_pilih}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else: st.warning("Tidak ditemukan data absensi pada periode bulan ini.")

    with tabs[6]:
        st.subheader("Registrasi & Manajemen Akun Guru")
        col_input, col_list = st.columns([1, 2])
        with col_input:
            st.markdown("#### ➕ Tambah Guru Baru")
            with st.form("tambah_guru", clear_on_submit=True):
                u_guru = st.text_input("Username Guru (NIP)")
                p_guru = st.text_input("Password Baru", type="password")
                n_guru = st.text_input("Nama Lengkap Guru")
                k_guru = st.text_input("Tugas di Kelas (Isi 'SEMUA' untuk Guru Piket / Guru Mapel)")
                submit_guru = st.form_submit_button("Daftarkan Akun")
                if submit_guru and u_guru and p_guru and k_guru:
                    if len(p_guru) < 6: st.error("Password wajib minimal 6 karakter.")
                    else:
                        hashed_p_guru = hash_password(p_guru)
                        try:
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute("INSERT INTO users VALUES (?, ?, 'Guru', ?, ?)", (u_guru, hashed_p_guru, n_guru, k_guru.strip().upper()))
                            conn.commit()
                            st.success(f"Akun {n_guru} berhasil didaftarkan!")
                            st.rerun()
                        except sqlite3.IntegrityError: st.error("Username/NIP sudah terdaftar.")
                        finally: conn.close()
        with col_list:
            st.markdown("#### 📋 Daftar Akun Guru Aktif")
            conn = get_db_connection()
            df_guru = pd.read_sql_query("SELECT username as [Username/NIP], nama as [Nama Guru], kelas_tugas as [Kelas Tugas] FROM users WHERE role='Guru'", conn)
            conn.close()
            if not df_guru.empty:
                for idx, row in df_guru.iterrows():
                    kelas_tampil = row['Kelas Tugas'] if row['Kelas Tugas'] else "Belum Set"
                    with st.expander(f"👤 {row['Nama Guru']} [Akses: {kelas_tampil}]"):
                        with st.form(f"form_edit_{row['Username/NIP']}"):
                            edit_nama = st.text_input("Nama Lengkap Baru", value=row['Nama Guru'])
                            edit_kelas = st.text_input("Kelas Tugas Baru", value=kelas_tampil)
                            edit_pass = st.text_input("Password Baru (Kosongkan jika tetap)", type="password")
                            check_hapus = st.checkbox("Saya ingin menghapus akun ini", key=f"del_chk_{row['Username/NIP']}")
                            
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                btn_simpan = st.form_submit_button("💾 Simpan Perubahan", use_container_width=True)
                            with col_btn2:
                                btn_hapus = st.form_submit_button("🗑️ Hapus Akun Ini", use_container_width=True)
                                
                            if btn_simpan:
                                conn = get_db_connection()
                                c = conn.cursor()
                                if edit_pass.strip() != "":
                                    c.execute("UPDATE users SET nama=?, kelas_tugas=?, password=? WHERE username=?", (edit_nama, edit_kelas.strip().upper(), hash_password(edit_pass), row['Username/NIP']))
                                else:
                                    c.execute("UPDATE users SET nama=?, kelas_tugas=? WHERE username=?", (edit_nama, edit_kelas.strip().upper(), row['Username/NIP']))
                                conn.commit()
                                conn.close()
                                st.success("Data diperbarui!")
                                st.rerun()
                            if btn_hapus and check_hapus:
                                conn = get_db_connection()
                                c = conn.cursor()
                                c.execute("DELETE FROM users WHERE username=?", (row['Username/NIP'],))
                                conn.commit()
                                conn.close()
                                st.rerun()

# ==========================================
# INTERFACE: MENU GURU
# ==========================================
elif st.session_state.role == "Guru":
    st.title("👨‍🏫 Panel Manajemen Guru")
    
    menu_guru = st.sidebar.radio("Pilih Menu", [
        "📝 Input Absensi Harian", 
        "🚨 Rekap Siswa Bermasalah Kelas Saya", 
        "📬 Pojok Curhat & Saran ke Kepsek",
        "📑 Rekap Bulanan Kelas Saya", 
        "📥 Sinkronisasi Data Dapodik"
    ])
    
    hak_akses = st.session_state.kelas_tugas.strip().upper()
    conn = get_db_connection()
    list_kelas_db = [r[0] for r in conn.execute("SELECT DISTINCT kelas FROM siswa WHERE kelas != '' AND kelas != '-'").fetchall()]
    conn.close()
    if not list_kelas_db: list_kelas_db = ["6A"]
        
    if hak_akses == "SEMUA": pilihan_kelas = st.sidebar.selectbox("Pilih Kelas Sasaran", list_kelas_db)
    else: pilihan_kelas = hak_akses

    hari_ini = str(datetime.date.today())

    # --------------------------------------
    # SUBMENU GURU: REKAP SISWA BERMASALAH KELAS SAYA (UTUH)
    # --------------------------------------
    if menu_guru == "🚨 Rekap Siswa Bermasalah Kelas Saya":
        st.subheader(f"🚨 Daftar Siswa Bermasalah (Sering Alpa) — Kelas {pilihan_kelas}")
        st.write("Siswa di bawah ini diurutkan berdasarkan akumulasi ketidakhadiran (Alpa) paling tinggi di kelas Anda.")
        
        conn = get_db_connection()
        df_kronis_guru = pd.read_sql_query('''
            SELECT s.nisn as [NISN], s.nama as [Nama Siswa], s.no_wa_orang_tua as [WA Orang Tua],
                   COUNT(a.id) as [Total Alpa]
            FROM siswa s
            JOIN absensi a ON s.nisn = a.nisn
            WHERE s.kelas = ? AND LOWER(a.status) = 'tidak_hadir'
            GROUP BY s.nisn
            ORDER BY [Total Alpa] DESC
        ''', conn, params=(pilihan_kelas,))
        conn.close()
        
        if df_kronis_guru.empty:
            st.success(f"Alhamdulillah! Tidak ada siswa kelas {pilihan_kelas} yang memiliki riwayat Alpa.")
        else:
            st.dataframe(df_kronis_guru, use_container_width=True)

    # --------------------------------------
    # SUBMENU GURU: POJOK CURHAT & KOTAK SARAN RAHASIA (UTUH)
    # --------------------------------------
    elif menu_guru == "📬 Pojok Curhat & Saran ke Kepsek":
        st.subheader("📬 Pojok Curhat & Kotak Saran Guru (Rahasia & Langsung ke Kepsek)")
        st.write("Punya kendala belajar, saran sekolah, atau komplain kehadiran guru lain yang enggan dibahas saat rapat? Sampaikan di sini secara tertutup.")
        
        with st.form("form_curhat_guru", clear_on_submit=True):
            kategori_aduan = st.selectbox("Pilih Kategori Penyampaian:", ["Masalah Siswa/Wali Murid", "Saran Sarana & Prasarana", "Komplain Kedisiplinan Guru/Staf", "Curhat Masalah Pribadi"])
            isi_aduan = st.text_area("Tuliskan pesan, kronologi, atau saran Anda secara lengkap:")
            
            if st.form_submit_button("🚀 Kirim Rahasia ke Kepala Sekolah"):
                if isi_aduan.strip() == "":
                    st.error("Isi pesan tidak boleh kosong!")
                else:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO aduan_curhat (tanggal, guru_pengirim, jenis_aduan, isi_curhat) VALUES (?, ?, ?, ?)",
                              (hari_ini, st.session_state.nama, kategori_aduan, isi_aduan))
                    conn.commit()
                    conn.close()
                    st.success("Sukses! Pesan Anda telah terkirim langsung ke meja digital Kepala Sekolah.")
        
        st.write("---")
        st.markdown("#### 📜 Riwayat Tanggapan Kepala Sekolah")
        conn = get_db_connection()
        df_riwayat_curhat = pd.read_sql_query("SELECT tanggal as [Tanggal], jenis_aduan as [Kategori], isi_curhat as [Aduan Saya], status_tindak_lanjut as [Status Kepsek], catatan_kepsek as [Tanggapan Kepsek] FROM aduan_curhat WHERE guru_pengirim = ? ORDER BY id DESC", conn, params=(st.session_state.nama,))
        conn.close()
        
        if df_riwayat_curhat.empty:
            st.caption("Belum ada riwayat curhat sebelumnya.")
        else:
            st.dataframe(df_riwayat_curhat, use_container_width=True)

    # --------------------------------------
    # SUBMENU GURU: REKAP BULANAN (UTUH)
    # --------------------------------------
    elif menu_guru == "📑 Rekap Bulanan Kelas Saya":
        st.subheader(f"📑 Menu Rekapitulasi Kehadiran Bulanan — Kelas {pilihan_kelas}")
        col_g1, col_g2 = st.columns(2)
        with col_g1: g_bulan = st.selectbox("Pilih Bulan", [f"{i:02d}" for i in range(1, 13)], index=datetime.date.today().month - 1, key="g_bln")
        with col_g2: g_tahun = st.selectbox("Pilih Tahun", [str(datetime.date.today().year), str(datetime.date.today().year - 1)], key="g_thn")
        g_periode = f"{g_tahun}-{g_bulan}-%"
        if st.button("📊 Unduh Rekapan Excel Kelas Saya", type="primary", use_container_width=True):
            conn = get_db_connection()
            df_rekap_guru = pd.read_sql_query('''
                SELECT s.kelas as [Kelas], s.nisn as [NISN], s.nama as [Nama Siswa],
                       SUM(CASE WHEN LOWER(a.status) = 'hadir' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as [Total Hadir],
                       SUM(CASE WHEN LOWER(a.status) = 'sakit' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as [Total Sakit/Izin],
                       SUM(CASE WHEN LOWER(a.status) = 'tidak_hadir' AND a.jam_ke = 'Harian' THEN 1 ELSE 0 END) as [Total Alpa]
                FROM siswa s
                LEFT JOIN absensi a ON s.nisn = a.nisn AND a.tanggal LIKE ?
                WHERE s.kelas = ?
                GROUP BY s.nisn
                ORDER BY s.nama ASC
            ''', conn, params=(g_periode, pilihan_kelas))
            conn.close()
            if not df_rekap_guru.empty:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_rekap_guru.to_excel(writer, sheet_name='Rekap', index=False)
                st.download_button(label=f"📥 Download File Excel Kelas {pilihan_kelas}", data=buffer.getvalue(), file_name=f"Rekap_{pilihan_kelas}_{g_bulan}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            else: st.warning("Tidak ditemukan data absensi periode bulan ini.")

    # --------------------------------------
    # SUBMENU GURU: SINKRONISASI DATA DAPODIK (UTUH & LENGKAP FITUR LAMA)
    # --------------------------------------
    elif menu_guru == "📥 Sinkronisasi Data Dapodik":
        st.subheader(f"Unggah Template Siswa Khusus Kelas {pilihan_kelas}")
        columns_template = ['Kelas', 'Nama', 'NISN', 'NIS', 'Tempat Lahir', 'Tanggal Lahir', 'Agama', 'NIK', 'Alamat', 'Nama Ayah', 'Pekerjaan Ayah', 'Nama Ibu', 'Pekerjaan Ibu', 'No WA Orang Tua']
        df_tpl = pd.DataFrame(columns=columns_template)
        tpl_buffer = io.BytesIO()
        with pd.ExcelWriter(tpl_buffer, engine='openpyxl') as writer: df_tpl.to_excel(writer, index=False)
        st.download_button(label="📄 Download Format Template Excel Dapodik", data=tpl_buffer.getvalue(), file_name=f"template_dapodik_kelas_{pilihan_kelas}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        uploaded_file = st.file_uploader("Upload File Excel Template Dapodik (.xlsx)", type=["xlsx"])
        if uploaded_file is not None:
            try:
                df_excel = pd.read_excel(uploaded_file)
                conn = get_db_connection()
                c = conn.cursor()
                sukses_import = 0
                for _, row in df_excel.iterrows():
                    if pd.isna(row['NISN']) or pd.isna(row['Nama']): continue
                    row = row.fillna('-')
                    c.execute('''INSERT OR REPLACE INTO siswa VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (str(row['NISN']).strip(), str(row['Nama']).strip(), str(row['Kelas']).strip().upper(), str(row['NIS']).strip(), str(row['Tempat Lahir']), str(row['Tanggal Lahir']), str(row['Agama']), str(row['NIK']), str(row['Alamat']), str(row['Nama Ayah']), str(row['Pekerjaan Ayah']), str(row['Nama Ibu']), str(row['Pekerjaan Ibu']), str(row['No WA Orang Tua']).strip()))
                    sukses_import += 1
                conn.commit()
                conn.close()
                st.success(f"Berhasil mengimpor {sukses_import} data siswa.")
            except Exception as e: st.error(f"Gagal membaca file: {e}")

        st.write("---")
        st.subheader(f"Tambah Siswa Secara Manual ke Kelas {pilihan_kelas}")
        with st.form("manual_siswa"):
            col1, col2 = st.columns(2)
            with col1:
                m_nama = st.text_input("Nama Lengkap Siswa")
                m_nisn = st.text_input("NISN")
                m_nis = st.text_input("NIS")
                m_wa = st.text_input("No WA Orang Tua")
            with col2:
                m_tl = st.text_input("Tempat Lahir")
                m_tgl = st.text_input("Tanggal Lahir")
                m_alamat = st.text_area("Alamat Rumah")
                
            submit_manual = st.form_submit_button("Simpan Data Siswa")
            if submit_manual and m_nisn and m_nama:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO siswa (nisn, nama, kelas, nis, tempat_lahir, tanggal_lahir, no_wa_orang_tua, alamat) VALUES (?,?,?,?,?,?,?,?)",
                          (m_nisn, m_nama, pilihan_kelas, m_nis, m_tl, m_tgl, m_wa, m_alamat))
                conn.commit()
                conn.close()
                st.success(f"Siswa {m_nama} berhasil dimasukkan ke kelas {pilihan_kelas}!")

    # --------------------------------------
    # SUBMENU GURU: INPUT ABSENSI HARIAN (LENGKAP SEMUA FORM EDIT & TAMBAH CEPAT)
    # --------------------------------------
    elif menu_guru == "📝 Input Absensi Harian":
        st.subheader(f"Isi Kehadiran Kelas Real-time")
        mode_absen = st.radio("Pilih Mode Pengisian Absen:", ["Wali Kelas / Umum (Harian)", "Mata Pelajaran (Per Jam Pelajaran)"], horizontal=True)
        if mode_absen == "Mata Pelajaran (Per Jam Pelajaran)":
            col_mp1, col_mp2 = st.columns(2)
            with col_mp1: val_mapel = st.selectbox("Mata Pelajaran", ["Bahasa Indonesia", "Matematika", "IPA", "IPS", "Bahasa Inggris", "Pendidikan Agama", "PJOK", "Seni Budaya"])
            with col_mp2: val_jam = st.selectbox("Jam Pelajaran Ke-", ["1-2 (07.00-08.20)", "3-4 (08.40-10.00)", "5-6 (10.20-11.40)", "7-8 (12.10-13.30)"])
            konteks_wa = f"Jam Pelajaran {val_jam} untuk Mata Pelajaran {val_mapel}"
        else:
            val_mapel = "Wali Kelas / Umum"
            val_jam = "Harian"
            konteks_wa = "Hari ini (Absensi Umum)"
            
        st.info(f"📋 **Kelas:** {pilihan_kelas} | 📚 **Mode:** {val_mapel} ({val_jam}) | 📅 **Tanggal:** {hari_ini}")
        
        # FITUR LAMA: EXPANDER TAMBAH SISWA DI TENGAH SEMESTER (DIPERTAHANKAN UTUH)
        with st.expander("➕ Tambah Siswa Baru Di Tengah Semester"):
            with st.form(f"form_cepat_tambah_{pilihan_kelas}", clear_on_submit=True):
                c_nama = st.text_input("Nama Lengkap Siswa Baru")
                c_nisn = st.text_input("NISN Siswa Baru")
                c_wa = st.text_input("No WA Orang Tua")
                submit_cepat = st.form_submit_button("Simpan Siswa Baru")
                
                if submit_cepat and c_nama and c_nisn:
                    conn = get_db_connection()
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO siswa (nisn, nama, kelas, no_wa_orang_tua) VALUES (?, ?, ?, ?)", 
                                  (c_nisn, c_nama, pilihan_kelas, c_wa))
                        conn.commit()
                        st.success(f"Berhasil menambahkan {c_nama} ke kelas {pilihan_kelas}!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Gagal! NISN sudah terdaftar.")
                    finally:
                        conn.close()
        
        conn = get_db_connection()
        query = '''
            SELECT s.nisn, s.nama, s.no_wa_orang_tua, s.nis, s.kelas, a.status 
            FROM siswa s 
            LEFT JOIN absensi a ON s.nisn = a.nisn AND a.tanggal = ? AND a.mapel = ? AND a.jam_ke = ?
            WHERE s.kelas = ?
            ORDER BY s.nama ASC
        '''
        df_siswa_kelas = pd.read_sql_query(query, conn, params=(hari_ini, val_mapel, val_jam, pilihan_kelas))
        conn.close()
        
        if df_siswa_kelas.empty:
            st.warning(f"Belum ada data siswa di Kelas {pilihan_kelas}. Silakan upload melalui menu Dapodik terlebih dahulu.")
            st.stop()
            
        col_bulk, _ = st.columns([2, 2])
        with col_bulk:
            if st.button("⚡ Tandai Semua Siswa Belum Absen sebagai 'HADIR'", use_container_width=True):
                waktu_sekarang = datetime.datetime.now().strftime("%H:%M:%S")
                conn = get_db_connection()
                c = conn.cursor()
                bulk_count = 0
                for _, row in df_siswa_kelas.iterrows():
                    status_db = str(row['status']).strip().lower() if row['status'] else 'belum'
                    if status_db not in ['hadir', 'sakit', 'tidak_hadir']:
                        c.execute('''INSERT OR REPLACE INTO absensi (nisn, tanggal, mapel, jam_ke, status, waktu, guru_input) 
                                     VALUES (?, ?, ?, ?, 'hadir', ?, ?)''', (row['nisn'], hari_ini, val_mapel, val_jam, waktu_sekarang, st.session_state.username))
                        bulk_count += 1
                conn.commit()
                conn.close()
                st.success(f"Berhasil menandai {bulk_count} siswa sebagai Hadir!")
                st.rerun()
                
        st.markdown("---")
        for idx, row in df_siswa_kelas.iterrows():
            status_clean = str(row['status']).strip().lower() if row['status'] else 'belum'
            if status_clean not in ['hadir', 'sakit', 'tidak_hadir', 'belum']: status_clean = 'belum'
            bg_color = "#FEE2E2" if status_clean == "tidak_hadir" else "#FFFFFF"
            
            with st.container():
                st.markdown(f"""<div style='background-color: {bg_color}; padding: 12px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #E5E7EB;'>""", unsafe_allow_html=True)
                col_nama, col_status, col_opsi, col_crud = st.columns([3, 2, 2, 2])
                with col_nama:
                    st.write(f"**{idx+1}. {row['nama']}**")
                    st.caption(f"NISN: {row['nisn']} | WA: {row['no_wa_orang_tua']}")
                with col_status:
                    idx_default = ['hadir', 'sakit', 'tidak_hadir', 'belum'].index(status_clean)
                    status_phelan = st.radio(f"Status {row['nisn']}", ['hadir', 'sakit', 'tidak_hadir', 'belum'], index=idx_default, key=f"status_{row['nisn']}_{val_mapel}_{val_jam}", label_visibility="collapsed", horizontal=True)
                    if status_phelan != status_clean:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute('''INSERT OR REPLACE INTO absensi (nisn, tanggal, mapel, jam_ke, status, waktu, guru_input) VALUES (?, ?, ?, ?, ?, ?, ?)''', (row['nisn'], hari_ini, val_mapel, val_jam, status_phelan, datetime.datetime.now().strftime("%H:%M:%S"), st.session_state.username))
                        conn.commit()
                        conn.close()
                        st.rerun()
                with col_opsi:
                    if status_phelan == 'tidak_hadir':
                        url_wa = kirim_wa_link(row['no_wa_orang_tua'], row['nama'], pilihan_kelas, "Alpa", konteks_wa)
                        st.markdown(f"👉 [💬 Hubungi WA Ortu]({url_wa})")
                        catatan_lap = st.text_input("Catatan", key=f"catatan_{row['nisn']}_{val_mapel}_{val_jam}", placeholder="Tindak lanjut...", label_visibility="collapsed")
                        if st.button("Kirim ke Kepsek", key=f"btn_lap_{row['nisn']}_{val_mapel}_{val_jam}"):
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute("INSERT INTO laporan_tindak_lanjut (nisn, tanggal, catatan, status_wa) VALUES (?, ?, ?, 'Sudah Dihubungi')", (row['nisn'], hari_ini, f"[{val_mapel}] {catatan_lap}"))
                            conn.commit()
                            conn.close()
                            st.success("Terkirim!")
                    elif status_phelan == 'hadir': st.write("✅ Hadir")
                    elif status_phelan == 'sakit': st.write("🤒 Sakit")
                    else: st.write("⏳ Belum Absen")
                    
                # FITUR LAMA: KELOLA EDIT DATA SISWA & HAPUS MANUAL (DIPERTAHANKAN UTUH & AMAN)
                with col_crud:
                    with st.expander("⚙️ Kelola"):
                        with st.form(f"form_crud_siswa_{row['nisn']}"):
                            st.markdown("**Edit Informasi Siswa**")
                            e_nama_sis = st.text_input("Nama Siswa", value=row['nama'])
                            e_wa_sis = st.text_input("No WA Orang Tua", value=row['no_wa_orang_tua'])
                            e_kelas_sis = st.text_input("Kelas", value=row['kelas'])
                            check_hapus_sis = st.checkbox("Centang untuk menghapus siswa ini", key=f"del_sis_chk_{row['nisn']}")
                            
                            c_btn1, c_btn2 = st.columns(2)
                            with c_btn1:
                                btn_save_sis = st.form_submit_button("💾 Update")
                            with c_btn2:
                                btn_del_sis = st.form_submit_button("🗑️ Hapus")
                                
                            if btn_save_sis:
                                conn = get_db_connection()
                                c = conn.cursor()
                                c.execute("UPDATE siswa SET nama=?, no_wa_orang_tua=?, kelas=? WHERE nisn=?", 
                                          (e_nama_sis, e_wa_sis, e_kelas_sis.strip().upper(), row['nisn']))
                                conn.commit()
                                conn.close()
                                st.success("Data siswa diperbarui!")
                                st.rerun()
                                
                            if btn_del_sis:
                                if check_hapus_sis:
                                    conn = get_db_connection()
                                    c = conn.cursor()
                                    c.execute("DELETE FROM absensi WHERE nisn=?", (row['nisn'],))
                                    c.execute("DELETE FROM laporan_tindak_lanjut WHERE nisn=?", (row['nisn'],))
                                    c.execute("DELETE FROM siswa WHERE nisn=?", (row['nisn'],))
                                    conn.commit()
                                    conn.close()
                                    st.success("Siswa dihapus!")
                                    st.rerun()
                                else:
                                    st.error("Wajib centang kotak konfirmasi!")
                st.markdown("</div>", unsafe_allow_html=True)