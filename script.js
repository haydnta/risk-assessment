// --- GLOBAL SCOPE VARIABLES ---
let currentTableData = []; 
let currentSortColumn = null; 
let currentSortDirection = 'asc';
let lastApiResponseData = null; 
// --- AKHIR GLOBAL SCOPE VARIABLES ---


document.addEventListener('DOMContentLoaded', () => {
    // --- Elemen HTML Umum ---
    const checkRiskBtn = document.getElementById('checkRiskBtn');
    const identityInput = document.getElementById('identityInput');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const resultSection = document.getElementById('resultSection');

    // --- Elemen untuk Risk Summary ---
    const overallScore = document.getElementById('overallScore');
    const riskLevel = document.getElementById('riskLevel');
    const scoreCircle = document.querySelector('.score-circle');
    const displayNik = document.getElementById('displayNik');
    const displayEmail = document.getElementById('displayEmail');
    const displayPhone = document.getElementById('displayPhone');
    const displayRecommendation = document.getElementById('displayRecommendation');

    // --- Elemen untuk Fraud Indicators ---
    const fraudIndicatorsContainer = document.getElementById('fraudIndicatorsContainer');

    // --- Elemen untuk Related Anomalies (Umum) ---
    const hubDetailsContainer = document.getElementById('hubDetailsContainer');
    const problematicNikWarning = document.getElementById('problematicNikWarning');
    const problematicNikList = document.getElementById('problematicNikList');
    const connectedUsersTableWrapper = document.getElementById('connectedUsersTableWrapper');
    const connectedUsersTableBody = document.getElementById('connectedUsersTableBody');
    const tableHeaders = document.querySelectorAll('.connected-users-table th[data-sort-key]');

    // --- Elemen untuk Hub Details ---
    const hubType = document.getElementById('hubType');
    const hubValue = document.getElementById('hubValue');
    const numConnectedUsers = document.getElementById('numConnectedUsers');

    // --- Elemen untuk Single NIK Details ---
    const singleNikDetails = document.getElementById('singleNikDetails');
    const companyIdDisplay = document.getElementById('companyIdDisplay');
    const nikConnectedEmails = document.getElementById('nikConnectedEmails');
    const emailsForNikList = document.getElementById('emailsForNikList');
    const nikConnectedPhones = document.getElementById('nikConnectedPhones');
    const phonesForNikList = document.getElementById('phonesForNikList');

    // --- Elemen untuk Raw API Response Modal ---
    const viewRawApiBtn = document.getElementById('viewRawApiBtn');
    const rawApiResponseModal = document.getElementById('rawApiResponseModal');
    const closeModalBtn = document.getElementById('closeModalBtn');
    const rawApiResponsePre = document.getElementById('rawApiResponsePre');

    // --- Elemen untuk Graf Jaringan (Vis.js) ---
    const networkGraphContainer = document.getElementById('networkGraphContainer');
    const networkGraphDiv = document.getElementById('networkGraph');

    // --- Elemen untuk Login/Logout ---
    const loggedInUserDisplay = document.getElementById('loggedInUserDisplay');
    const logoutBtn = document.getElementById('logoutBtn');


    // --- FUNGSI AUTENTIKASI ---
    function checkAuthentication() {
        const isAuthenticated = sessionStorage.getItem('isAuthenticated');
        const loggedInUser = sessionStorage.getItem('loggedInUser');

        if (isAuthenticated === 'true' && loggedInUser) {
            loggedInUserDisplay.textContent = `Halo, ${loggedInUser}!`;
            // Lanjutkan ke dashboard
        } else {
            // Jika tidak terautentikasi, redirect ke halaman login
            window.location.href = '/login'; 
        }
    }

    function handleLogout() {
        sessionStorage.removeItem('isAuthenticated'); // Hapus status autentikasi
        sessionStorage.removeItem('loggedInUser'); // Hapus username
        window.location.href = '/logout'; // Redirect ke endpoint logout Flask (yang akan redirect ke /login)
    }

    // Panggil checkAuthentication saat halaman dimuat
    checkAuthentication();

    // Event listener untuk tombol logout
    logoutBtn.addEventListener('click', handleLogout);


    // --- Event Listener untuk Tombol "Cek Risiko" ---
    checkRiskBtn.addEventListener('click', async () => {
        const input = identityInput.value.trim();
        if (!input) {
            alert('Mohon masukkan NIK, Email, atau Nomor HP.');
            return;
        }

        loadingIndicator.style.display = 'block';
        resultSection.style.display = 'none';
        checkRiskBtn.disabled = true;

        try {
            const API_URL = 'http://127.0.0.1:5000/v1/risk/identity-check'; 

            const response = await fetch(API_URL, {
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ identity_input: input }),
            });

            if (!response.ok) {
                const errorText = await response.text();
                // Jika error 401 (Unauthorized), redirect ke login
                if (response.status === 401) {
                    alert('Sesi Anda telah berakhir atau tidak terautentikasi. Mohon login kembali.');
                    handleLogout(); // Bersihkan sesi dan redirect
                    return;
                }
                throw new Error(`HTTP Error ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            console.log("API Response Data:", data); 
            
            lastApiResponseData = data; 
            
            currentTableData = []; 
            if (data.related_anomalies && data.related_anomalies.hub_details && 
                (data.primary_entity_type === 'EMAIL_HUB' || data.primary_entity_type === 'PHONE_HUB')) {
                currentTableData = data.related_anomalies.hub_details.connected_users_details || [];
            }
            
            displayResults(data);

        } catch (error) {
            console.error('Error fetching data:', error); 
            alert('Gagal mengambil data risiko: ' + error.message); 
        } finally {
            loadingIndicator.style.display = 'none';
            checkRiskBtn.disabled = false;
        }
    });

    // --- Event Listener untuk Tombol "Lihat Raw API Response" ---
    viewRawApiBtn.addEventListener('click', () => {
        if (lastApiResponseData) {
            rawApiResponsePre.textContent = JSON.stringify(lastApiResponseData, null, 2);
            rawApiResponseModal.style.display = 'flex'; 
        } else {
            alert('Belum ada data API yang tersedia. Mohon lakukan asesmen risiko terlebih dahulu.');
        }
    });

    // --- Event Listener untuk Tombol Tutup Modal ---
    closeModalBtn.addEventListener('click', () => {
        rawApiResponseModal.style.display = 'none'; 
    });

    rawApiResponseModal.addEventListener('click', (event) => {
        if (event.target === rawApiResponseModal) { 
            rawApiResponseModal.style.display = 'none';
        }
    });

    // --- Fungsi Utama untuk Menampilkan Semua Hasil di UI ---
    function displayResults(data) {
        resultSection.style.display = 'block';

        // 1. Menampilkan Ringkasan Risiko Utama (Overall Risk Score)
        const score = data.overall_risk_score;
        const level = data.risk_level;
        overallScore.textContent = score;
        riskLevel.textContent = `${level} RISK`;

        let scoreColor = '#4CAF50'; 
        if (level === 'CRITICAL') {
            scoreColor = '#F44336'; 
        } else if (level === 'HIGH') {
            scoreColor = '#FF9800'; 
        } else if (level === 'MEDIUM') {
            scoreColor = '#FFEB3B'; 
        }
        scoreCircle.style.background = `conic-gradient(${scoreColor} ${score}%, #eee ${score}% 100%)`;
        overallScore.style.color = scoreColor; 
        riskLevel.style.color = scoreColor;

        displayNik.textContent = data.nik || 'N/A';
        displayEmail.textContent = data.email_input || 'N/A';
        displayPhone.textContent = data.phone_number_input || 'N/A';
        
        displayRecommendation.textContent = data.recommendation;
        if (data.recommendation === 'REVIEW_MANUAL') {
            displayRecommendation.style.backgroundColor = '#ff9800';
        } else if (data.recommendation === 'REJECT') {
            displayRecommendation.style.backgroundColor = '#dc3545';
        } else { 
            displayRecommendation.style.backgroundColor = '#28a745';
        }


        // 2. Menampilkan Indikator Kecurangan (Fraud Indicators)
        fraudIndicatorsContainer.innerHTML = ''; 
        if (data.fraud_indicators && data.fraud_indicators.length > 0) {
            data.fraud_indicators.forEach(indicator => {
                const card = document.createElement('div');
                card.classList.add('indicator-card', `impact-${indicator.impact}`); 
                
                let iconClass = 'fas fa-info-circle'; 
                if (indicator.type === 'SHARED_CONTACT_HUB') {
                    iconClass = 'fas fa-project-diagram';
                } else if (indicator.type === 'HUB_CONTAINS_PROBLEMATIC_NIKS') {
                    iconClass = 'fas fa-exclamation-circle';
                } else if (indicator.type === 'DUKCAPIL_MISMATCH') {
                    iconClass = 'fas fa-id-card-alt';
                } else if (indicator.type === 'SHARED_CONTACT' || indicator.type === 'MULTI_ACCOUNT_PHONE') {
                    iconClass = 'fas fa-users';
                } else if (indicator.type === 'MULTI_EMAIL_PER_NIK') {
                    iconClass = 'fas fa-envelope-open-text';
                } else if (indicator.type === 'MULTI_PHONE_PER_NIK') {
                    iconClass = 'fas fa-phone-square-alt';
                } else if (indicator.type === 'PROBLEM_DUKCAPIL_COMPANY') {
                    iconClass = 'fas fa-building';
                } else if (indicator.type === 'EMAIL_NOT_UNIQUE_PER_COMPANY_SUCCESS_KYC') {
                    iconClass = 'fas fa-exclamation-triangle';
                } else if (indicator.type === 'FRAUD_RING_MEMBERSHIP') {
                    iconClass = 'fas fa-skull-crossbones';
                }
                
                card.innerHTML = `
                    <div class="icon-type">
                        <i class="${iconClass}"></i>
                        <span>${indicator.type.replace(/_/g, ' ')}</span>
                    </div>
                    <div class="detail">${indicator.detail}</div>
                `;
                fraudIndicatorsContainer.appendChild(card);
            });
        } else {
            fraudIndicatorsContainer.innerHTML = '<p>Tidak ada indikator kecurangan yang ditemukan.</p>';
        }

        // 3. Menampilkan Detail Anomali Terkait (berdasarkan primary_entity_type)
        networkGraphContainer.style.display = 'none'; 
        hubDetailsContainer.style.display = 'none';
        connectedUsersTableWrapper.style.display = 'none';
        problematicNikWarning.style.display = 'none';
        singleNikDetails.style.display = 'none';
        nikConnectedEmails.style.display = 'none';
        nikConnectedPhones.style.display = 'none';

        if (data.primary_entity_type === 'EMAIL_HUB' || data.primary_entity_type === 'PHONE_HUB') {
            if (data.related_anomalies && data.related_anomalies.hub_details) {
                hubDetailsContainer.style.display = 'flex'; 
                const hubDetails = data.related_anomalies.hub_details;
                hubType.textContent = hubDetails.hub_type || 'N/A';
                hubValue.textContent = hubDetails.hub_value || 'N/A';
                numConnectedUsers.textContent = hubDetails.num_connected_users || '0';
                
                connectedUsersTableWrapper.style.display = 'block'; 
                renderConnectedUsersTable(currentTableData); 

                networkGraphContainer.style.display = 'block';
                drawNetworkGraph(hubDetails.connected_users_details, hubDetails.hub_value, hubDetails.hub_type);
            }
            if (data.related_anomalies.hub_problematic_niks && data.related_anomalies.hub_problematic_niks.length > 0) {
                problematicNikWarning.style.display = 'block';
                problematicNikList.innerHTML = '';
                data.related_anomalies.hub_problematic_niks.forEach(nik => {
                    const li = document.createElement('li');
                    li.textContent = nik;
                    problematicNikList.appendChild(li);
                });
            }
        } else if (data.primary_entity_type === 'SINGLE_NIK') {
            singleNikDetails.style.display = 'block'; 

            if (data.related_anomalies && data.related_anomalies.company_details) {
                companyIdDisplay.textContent = data.related_anomalies.company_details.company_id || 'N/A';
            } else {
                companyIdDisplay.textContent = 'Tidak Ada';
            }

            if (data.related_anomalies && data.related_anomalies.emails_for_nik && data.related_anomalies.emails_for_nik.length > 0) {
                nikConnectedEmails.style.display = 'block';
                emailsForNikList.innerHTML = '';
                data.related_anomalies.emails_for_nik.forEach(email => {
                    const li = document.createElement('li');
                    li.textContent = email;
                    emailsForNikList.appendChild(li);
                });
            } else {
                nikConnectedEmails.style.display = 'none'; 
            }

            if (data.related_anomalies && data.related_anomalies.phones_for_nik && data.related_anomalies.phones_for_nik.length > 0) {
                nikConnectedPhones.style.display = 'block';
                phonesForNikList.innerHTML = '';
                data.related_anomalies.phones_for_nik.forEach(phone => {
                    const li = document.createElement('li');
                    li.textContent = phone;
                    phonesForNikList.appendChild(li);
                });
            } else {
                nikConnectedPhones.style.display = 'none'; 
            }

            networkGraphContainer.style.display = 'block';
            drawSingleNikNetworkGraph(data.nik, data.related_anomalies);

        } else {
            console.warn("Unknown primary_entity_type or missing data:", data.primary_entity_type);
        }
    }

    // --- Fungsi untuk Merender Ulang Tabel Pengguna Terhubung ---
    function renderConnectedUsersTable(users) {
        connectedUsersTableBody.innerHTML = ''; 

        if (users && users.length > 0) {
            users.forEach(user => {
                const row = document.createElement('tr'); 

                let dukcapilStatusClass = '';
                if (user.dukcapil_response && user.dukcapil_response.toLowerCase().includes('sukses')) {
                    dukcapilStatusClass = 'dukcapil-status-success';
                } else {
                    dukcapilStatusClass = 'dukcapil-status-fail';
                }

                const scoreWidth = user.dukcapil_score ? (user.dukcapil_score / 15 * 100) : 0; 
                let scoreBarColor = '';
                if (scoreWidth > 70) scoreBarColor = '#28a745'; 
                else if (scoreWidth > 40) scoreBarColor = '#ffc107'; 
                else scoreBarColor = '#dc3545'; 

                let certTagClass = 'certificate-tag-unknown';
                if (user.certificate_status === 'not-active') {
                    certTagClass = 'certificate-tag-not-active';
                } else if (user.certificate_status === 'expired') {
                    certTagClass = 'certificate-tag-expired';
                } else if (user.certificate_status === 'active') {
                    certTagClass = 'certificate-tag-active';
                }

                row.innerHTML = `
                    <td data-label="NIK">${user.nik || 'N/A'}</td>
                    <td data-label="Dukcapil Response" class="${dukcapilStatusClass}">${user.dukcapil_response || 'N/A'}</td>
                    <td data-label="Skor Dukcapil">
                        <div class="score-bar-container">
                            <div class="score-bar" style="width: ${scoreWidth}%; background-color: ${scoreBarColor};"></div>
                        </div>
                        <span style="font-size:0.8em; margin-left:5px;">${user.dukcapil_score ? user.dukcapil_score.toFixed(2) : 'N/A'}</span>
                    </td>
                    <td data-label="Status Sertifikat"><span class="certificate-tag ${certTagClass}">${user.certificate_status || 'N/A'}</span></td>
                    <td data-label="Email Lainnya">${user.other_emails && user.other_emails.length > 0 ? user.other_emails.join(', ') : 'N/A'}</td>
                `;
                connectedUsersTableBody.appendChild(row); 
            });
        } else {
            connectedUsersTableBody.innerHTML = '<tr><td colspan="5">Tidak ada pengguna terhubung.</td></tr>';
        }
    }


    // --- Logika Sorting Tabel ---
    tableHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const sortKey = header.dataset.sortKey; 

            if (currentSortColumn === sortKey) {
                currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                currentSortColumn = sortKey;
                currentSortDirection = 'asc'; 
            }

            tableHeaders.forEach(th => {
                th.classList.remove('sorted-asc', 'sorted-desc');
                const icon = th.querySelector('.sort-icon');
                if (icon) {
                    icon.classList.remove('fa-sort-up', 'fa-sort-down');
                    icon.classList.add('fa-sort'); 
                }
            });

            header.classList.add(`sorted-${currentSortDirection}`);
            const activeIcon = header.querySelector('.sort-icon');
            if (activeIcon) {
                activeIcon.classList.remove('fa-sort');
                activeIcon.classList.add(currentSortDirection === 'asc' ? 'fa-sort-up' : 'fa-sort-down');
            }

            sortConnectedUsers(sortKey, currentSortDirection);
        });
    });

    function sortConnectedUsers(key, direction) {
        if (!currentTableData || currentTableData.length === 0) {
            console.warn('Tidak ada data untuk diurutkan.');
            renderConnectedUsersTable([]); 
            return;
        }

        currentTableData.sort((a, b) => {
            let valA = a[key]; 
            let valB = b[key]; 

            if (key === 'dukcapil_score') {
                valA = parseFloat(valA) || 0; 
                valB = parseFloat(valB) || 0;
            } 
            else if (typeof valA === 'string' && typeof valB === 'string') {
                valA = valA.toLowerCase();
                valB = valB.toLowerCase();
            }
            else if (key === 'emails_connected' || key === 'phones_connected' || key === 'other_emails') { 
                valA = (valA && Array.isArray(valA) && valA.length > 0) ? valA.join(', ').toLowerCase() : '';
                valB = (valB && Array.isArray(valB) && valB.length > 0) ? valB.join(', ').toLowerCase() : '';
            }
            if (valA == null) return direction === 'asc' ? 1 : -1;
            if (valB == null) return direction === 'asc' ? -1 : 1;


            if (valA < valB) {
                return direction === 'asc' ? -1 : 1; 
            }
            if (valA > valB) {
                return direction === 'asc' ? 1 : -1; 
            }
            return 0; 
        });

        renderConnectedUsersTable(currentTableData);
    }


    // --- Fungsi untuk Menggambar Graf Jaringan (Vis.js) ---
    function drawNetworkGraph(connectedUsersDetails, hubValue, hubType) {
        const nodes = [];
        const edges = [];
        let uniqueNodeIds = new Set(); 

        const hubNodeId = `hub_${hubValue}`;
        nodes.push({ 
            id: hubNodeId, 
            label: `${hubType.toUpperCase()}: ${hubValue}`, 
            group: hubType,
            font: { size: 18, color: '#0d47a1', face: 'Poppins' },
            color: { background: '#e3f2fd', border: '#0d47a1' },
            shape: 'box', 
            title: `Hub ${hubType}: ${hubValue} (Terhubung ke ${connectedUsersDetails.length} pengguna)`
        });
        uniqueNodeIds.add(hubNodeId);

        connectedUsersDetails.forEach(user => {
            const userNodeId = `user_${user.nik}`;
            if (!uniqueNodeIds.has(userNodeId)) {
                nodes.push({ 
                    id: userNodeId, 
                    label: `NIK: ${user.nik}`, 
                    group: 'user',
                    font: { size: 14, color: '#333', face: 'Poppins' },
                    color: { background: '#fffde7', border: '#ffc107' }, 
                    shape: 'dot', 
                    title: `NIK: ${user.nik}\nStatus: ${user.certificate_status}\nScore: ${user.dukcapil_score}`
                });
                uniqueNodeIds.add(userNodeId);
            }

            edges.push({ 
                from: userNodeId, 
                to: hubNodeId, 
                label: 'HAS_CONTACT', 
                color: { color: '#9e9e9e' },
                font: { align: 'middle' },
                arrows: 'to'
            });

            if (user.other_emails && user.other_emails.length > 0) {
                user.other_emails.forEach(email => {
                    const emailNodeId = `email_${email}`;
                    if (!uniqueNodeIds.has(emailNodeId)) {
                        nodes.push({
                            id: emailNodeId,
                            label: `Email: ${email}`,
                            group: 'email',
                            font: { size: 12, color: '#424242', face: 'Poppins' },
                            color: { background: '#fce4ec', border: '#e91e63' }, 
                            shape: 'ellipse', 
                            title: `Email: ${email}`
                        });
                        uniqueNodeIds.add(emailNodeId);
                    }
                    edges.push({ from: userNodeId, to: emailNodeId, label: 'HAS_EMAIL', color: { color: '#9e9e9e' }, font: { align: 'middle' }, arrows: 'to' });
                });
            }
        });

        const data = {
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(edges)
        };

        const options = {
            nodes: {
                borderWidth: 2,
                size: 30,
                font: { color: '#333' },
                shadow: true
            },
            edges: {
                width: 2,
                shadow: true,
                color: { inherit: 'from' }
            },
            physics: {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 95,
                    springConstant: 0.04,
                    damping: 0.09,
                    avoidOverlap: 0.5
                },
                solver: 'barnesHut'
            },
            interaction: {
                navigationButtons: true,
                keyboard: true
            },
            groups: {
                email: {
                    color: { background: '#fce4ec', border: '#e91e63' }, 
                    font: { color: '#333' }
                },
                phone: {
                    color: { background: '#e0f2f7', border: '#00bcd4' }, 
                    font: { color: '#333' }
                },
                user: {
                    color: { background: '#fffde7', border: '#ffc107' }, 
                    font: { color: '#333' }
                },
                company: {
                    color: { background: '#e8eaf6', border: '#3f51b5' }, 
                    font: { color: '#333' }
                }
            }
        };

        const network = new vis.Network(networkGraphDiv, data, options);
        network.fit(); 
    }

    // Fungsi untuk Menggambar Graf Jaringan untuk SINGLE_NIK (dari related_anomalies)
    function drawSingleNikNetworkGraph(nik, relatedAnomalies) {
        const nodes = [];
        const edges = [];
        let uniqueNodeIds = new Set();

        const mainNikNodeId = `user_${nik}`;
        nodes.push({
            id: mainNikNodeId,
            label: `NIK: ${nik}`,
            group: 'user',
            font: { size: 20, color: '#fff', face: 'Poppins', strokeWidth: 2, strokeColor: '#0d47a1' },
            color: { background: '#1a237e', border: '#0d47a1' }, 
            shape: 'star', 
            title: `NIK Utama: ${nik}`
        });
        uniqueNodeIds.add(mainNikNodeId);

        if (relatedAnomalies.company_details && relatedAnomalies.company_details.company_id) {
            const companyNodeId = `company_${relatedAnomalies.company_details.company_id}`;
            if (!uniqueNodeIds.has(companyNodeId)) {
                nodes.push({
                    id: companyNodeId,
                    label: `Company: ${relatedAnomalies.company_details.company_id}`,
                    group: 'company',
                    font: { size: 14, color: '#333', face: 'Poppins' },
                    color: { background: '#e8eaf6', border: '#3f51b5' },
                    shape: 'square', 
                    title: `Perusahaan: ${relatedAnomalies.company_details.company_name || relatedAnomalies.company_details.company_id}`
                });
                uniqueNodeIds.add(companyNodeId);
            }
            edges.push({ from: mainNikNodeId, to: companyNodeId, label: 'REGISTERED_VIA', color: { color: '#9e9e9e' }, font: { align: 'middle' }, arrows: 'to' });
        }

        if (relatedAnomalies.emails_for_nik && relatedAnomalies.emails_for_nik.length > 0) {
            relatedAnomalies.emails_for_nik.forEach(email => {
                const emailNodeId = `email_${email}`;
                if (!uniqueNodeIds.has(emailNodeId)) {
                    nodes.push({
                        id: emailNodeId,
                        label: `Email: ${email}`,
                        group: 'email',
                        font: { size: 12, color: '#424242', face: 'Poppins' },
                        color: { background: '#fce4ec', border: '#e91e63' }, 
                        shape: 'ellipse',
                        title: `Email: ${email}`
                    });
                    uniqueNodeIds.add(emailNodeId);
                }
                edges.push({ from: mainNikNodeId, to: emailNodeId, label: 'HAS_EMAIL', color: { color: '#9e9e9e' }, font: { align: 'middle' }, arrows: 'to' });
            });
        }

        if (relatedAnomalies.phones_for_nik && relatedAnomalies.phones_for_nik.length > 0) {
            relatedAnomalies.phones_for_nik.forEach(phone => {
                const phoneNodeId = `phone_${phone}`;
                if (!uniqueNodeIds.has(phoneNodeId)) {
                    nodes.push({
                        id: phoneNodeId,
                        label: `Phone: ${phone}`,
                        group: 'phone',
                        font: { size: 12, color: '#424242', face: 'Poppins' },
                        color: { background: '#e0f2f7', border: '#00bcd4' }, 
                        shape: 'ellipse',
                        title: `Phone: ${phone}`
                    });
                    uniqueNodeIds.add(phoneNodeId);
                }
                edges.push({ from: mainNikNodeId, to: phoneNodeId, label: 'HAS_PHONE', color: { color: '#9e9e9e' }, font: { align: 'middle' }, arrows: 'to' });
            });
        }

        if (relatedAnomalies.fraud_hubs && relatedAnomalies.fraud_hubs.length > 0) {
            relatedAnomalies.fraud_hubs.forEach(hub => {
                const fraudHubNodeId = `fraud_hub_${hub.hub_email || hub.hub_phone}`;
                if (!uniqueNodeIds.has(fraudHubNodeId)) {
                    nodes.push({
                        id: fraudHubNodeId,
                        label: `Fraud Hub: ${hub.hub_email || hub.hub_phone}`,
                        group: 'fraud_hub',
                        font: { size: 16, color: '#fff', face: 'Poppins' },
                        color: { background: '#c62828', border: '#b71c1c' }, 
                        shape: 'diamond', 
                        title: `Fraud Hub: ${hub.hub_email || hub.hub_phone}\nConnected Users: ${hub.num_connected_active_users}`
                    });
                    uniqueNodeIds.add(fraudHubNodeId);
                }
                edges.push({ from: mainNikNodeId, to: fraudHubNodeId, label: 'MEMBER_OF_FRAUD_HUB', color: { color: '#d32f2f' }, font: { align: 'middle' }, arrows: 'to' });
            });
        }

        const data = {
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(edges)
        };

        const options = {
            nodes: {
                borderWidth: 2,
                size: 30,
                font: { color: '#333' },
                shadow: true
            },
            edges: {
                width: 2,
                shadow: true,
                color: { inherit: 'from' }
            },
            physics: {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 95,
                    springConstant: 0.04,
                    damping: 0.09,
                    avoidOverlap: 0.5
                },
                solver: 'barnesHut'
            },
            interaction: {
                navigationButtons: true,
                keyboard: true
            },
            groups: {
                email: {
                    color: { background: '#fce4ec', border: '#e91e63' }, 
                    font: { color: '#333' }
                },
                phone: {
                    color: { background: '#e0f2f7', border: '#00bcd4' }, 
                    font: { color: '#333' }
                },
                user: {
                    color: { background: '#fffde7', border: '#ffc107' }, 
                    font: { color: '#333' }
                },
                company: {
                    color: { background: '#e8eaf6', border: '#3f51b5' }, 
                    font: { color: '#333' }
                },
                fraud_hub: {
                    color: { background: '#c62828', border: '#b71c1c' }, 
                    font: { color: '#fff' }
                }
            }
        };

        const network = new vis.Network(networkGraphDiv, data, options);
        network.fit();
    }
});
