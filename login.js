document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const loginMessage = document.getElementById('loginMessage');

    // --- KREDENSIAL HARDCODE (TIDAK AMAN UNTUK PRODUKSI!) ---
    const HARDCODED_USERNAME = 'denta';
    const HARDCODED_PASSWORD = 'peruri123';
    // --- AKHIR KREDENSIAL HARDCODE ---

    // Cek apakah pengguna sudah login (misalnya, jika mereka kembali ke halaman login setelah login)
    if (sessionStorage.getItem('isAuthenticated') === 'true') {
        // Jika sudah terautentikasi, langsung redirect ke dashboard
        window.location.href = '/risk-asses-v2/';
    }

    loginForm.addEventListener('submit', (e) => {
        e.preventDefault(); // Mencegah form submit secara default

        const username = usernameInput.value;
        const password = passwordInput.value;

        if (username === HARDCODED_USERNAME && password === HARDCODED_PASSWORD) {
            sessionStorage.setItem('isAuthenticated', 'true'); // Simpan status autentikasi
            sessionStorage.setItem('loggedInUser', username); // Simpan username
            loginMessage.textContent = 'Login berhasil! Mengarahkan ke dashboard...';
            loginMessage.style.color = '#4CAF50'; // Hijau untuk sukses
            window.location.href = '/risk-asses-v2/'; // Redirect ke dashboard
        } else {
            loginMessage.textContent = 'Username atau password salah.';
            loginMessage.style.color = '#e53935'; // Merah untuk error
        }
    });
});
