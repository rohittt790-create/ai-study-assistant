/**
 * AI Study Assistant - Client Application Controller
 */

class StudyApp {
    constructor() {
        this.token = localStorage.getItem('study_token') || null;
        this.currentUser = null;
        this.documents = [];
        this.activeDocId = null;
        this.activeDoc = null;
        this.currentSummary = "";
        this.currentQuiz = null;
        this.quizSelectedAnswers = {};
        this.quizSubmitted = false;
        this.flashcards = [];
        this.flashcardIndex = 0;
        this.quizMode = "mcq";
        this.savedNotes = [];
        this.authTab = "login";
        this.activeView = "dashboard";
    }

    async init() {
        // Initialize marked renderer options
        if (window.marked) {
            marked.setOptions({
                breaks: true,
                gfm: true
            });
        }

        this.initDropzone();
        
        // Check current session
        if (this.token) {
            await this.loadCurrentUser();
            await this.loadDocuments();
            await this.loadDashboardStats();
        } else {
            this.renderLoggedOutState();
        }

        this.renderAuthNav();
        this.loadDatabaseStatus();
        
        if (window.lucide) {
            lucide.createIcons();
        }
    }

    async loadDatabaseStatus() {
        try {
            const res = await this.api("/api/database/status");
            const badge = document.getElementById("mongoDbStatusBadge");
            if (badge && res) {
                if (res.connected) {
                    badge.className = "hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200";
                    badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1"></span> MongoDB Atlas Connected`;
                    badge.title = `Connected to ${res.cluster} (DB: ${res.database_name})`;
                } else {
                    badge.className = "hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200";
                    badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1"></span> Local Mirror Active`;
                }
            }
        } catch (e) {
            // silent ignore
        }
    }

    // ==========================================
    // API UTILITIES
    // ==========================================
    async api(endpoint, options = {}) {
        const headers = options.headers || {};
        if (this.token) {
            headers["Authorization"] = `Bearer ${this.token}`;
        }
        if (!options.isFormData && options.body && typeof options.body === 'object') {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(options.body);
        }

        try {
            const resp = await fetch(endpoint, {
                ...options,
                headers
            });

            if (resp.status === 401) {
                // Token expired
                this.token = null;
                localStorage.removeItem('study_token');
                this.currentUser = null;
                this.renderAuthNav();
                this.showToast("Session expired. Please log in.", "error");
                throw new Error("Unauthorized");
            }

            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.detail || data.message || "An error occurred");
            }
            return data;
        } catch (err) {
            console.error("API error:", err);
            throw err;
        }
    }

    showToast(message, type = "info") {
        const container = document.getElementById("toastContainer");
        if (!container) return;

        const toast = document.createElement("div");
        const colors = {
            success: "bg-emerald-600 text-white",
            error: "bg-red-600 text-white",
            info: "bg-slate-900 text-white"
        };
        toast.className = `px-4 py-3 rounded-xl shadow-lg text-xs font-semibold flex items-center space-x-2 transition-all duration-300 transform translate-y-2 opacity-0 pointer-events-auto ${colors[type] || colors.info}`;
        toast.innerHTML = `<span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.remove("translate-y-2", "opacity-0");
        }, 10);

        setTimeout(() => {
            toast.classList.add("opacity-0", "translate-y-2");
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    }

    // ==========================================
    // AUTHENTICATION
    // ==========================================
    async loadCurrentUser() {
        try {
            const res = await this.api("/api/auth/me");
            this.currentUser = res.user;
            this.updateUserUI(res);
        } catch (err) {
            this.currentUser = null;
        }
        this.renderAuthNav();
    }

    updateUserUI(res) {
        if (!this.currentUser) return;
        const nameEl = document.getElementById("dashUsername");
        if (nameEl) nameEl.textContent = this.currentUser.username;

        if (res && res.stats) {
            const d = document.getElementById("statDocsCount");
            const n = document.getElementById("statNotesCount");
            const q = document.getElementById("statQuizzesCount");
            const s = document.getElementById("statAvgScore");
            if (d) d.textContent = res.stats.documents_count || 0;
            if (n) n.textContent = res.stats.notes_count || 0;
            if (q) q.textContent = res.stats.quizzes_taken || 0;
            if (s) s.textContent = `${res.stats.avg_quiz_score || 0}%`;
        }
    }

    renderLoggedOutState() {
        this.documents = [];
        this.activeDocId = null;
        this.activeDoc = null;
        this.currentSummary = "";
        this.savedNotes = [];
        
        const nameEl = document.getElementById("dashUsername");
        if (nameEl) nameEl.textContent = "Guest Student";
        
        const d = document.getElementById("statDocsCount");
        const n = document.getElementById("statNotesCount");
        const q = document.getElementById("statQuizzesCount");
        const s = document.getElementById("statAvgScore");
        if (d) d.textContent = "0";
        if (n) n.textContent = "0";
        if (q) q.textContent = "0";
        if (s) s.textContent = "0%";
        
        const quizLabel = document.getElementById("quizSourceDocLabel");
        if (quizLabel) quizLabel.textContent = "Active Document: No doc selected";
        
        this.renderDocumentSelectors();
        this.renderDocumentLibrary();
        this.renderDashboardRecentDocs();
        
        const sidebarTitle = document.getElementById("sidebarActiveDocTitle");
        const sidebarMeta = document.getElementById("sidebarActiveDocMeta");
        if (sidebarTitle) sidebarTitle.textContent = "Please sign in";
        if (sidebarMeta) sidebarMeta.textContent = "Log in or register to study your notes.";
    }

    renderAuthNav() {
        const authDiv = document.getElementById("authActions");
        const sidebarUserCard = document.getElementById("sidebarUserCard");

        if (this.currentUser) {
            if (authDiv) {
                authDiv.innerHTML = `
                    <div class="flex items-center space-x-2.5">
                        <div class="text-right hidden sm:block">
                            <div class="text-xs font-bold text-slate-800">${this.currentUser.username}</div>
                            <div class="text-[10px] text-emerald-600 font-semibold">${this.currentUser.email}</div>
                        </div>
                        <div class="w-8 h-8 rounded-full bg-brand-600 text-white flex items-center justify-center font-bold text-xs shadow-xs">
                            ${this.currentUser.username.charAt(0).toUpperCase()}
                        </div>
                        <button onclick="app.logout()" class="px-3 py-1.5 text-xs font-bold text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 rounded-xl transition-all flex items-center shadow-xs" title="Sign Out of Account">
                            <i data-lucide="log-out" class="w-3.5 h-3.5 mr-1.5"></i>
                            <span>Log Out</span>
                        </button>
                    </div>
                `;
            }
            if (sidebarUserCard) {
                sidebarUserCard.innerHTML = `
                    <div class="flex items-center space-x-2.5 mb-2.5">
                        <div class="w-7 h-7 rounded-lg bg-brand-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0">
                            ${this.currentUser.username.charAt(0).toUpperCase()}
                        </div>
                        <div class="min-w-0 flex-1">
                            <div class="text-xs font-bold text-slate-800 truncate">${this.currentUser.username}</div>
                            <div class="text-[10px] text-slate-400 truncate">${this.currentUser.email}</div>
                        </div>
                    </div>
                    <button onclick="app.logout()" class="w-full py-1.5 px-2.5 text-xs font-semibold text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors flex items-center justify-center border border-red-200">
                        <i data-lucide="log-out" class="w-3.5 h-3.5 mr-1.5"></i> Log Out
                    </button>
                `;
            }
        } else {
            if (authDiv) {
                authDiv.innerHTML = `
                    <div class="flex items-center space-x-2">
                        <button onclick="app.openAuthModal('login')" class="px-3.5 py-1.5 text-xs font-bold text-slate-700 hover:text-brand-600 bg-white hover:bg-slate-50 border border-slate-300 hover:border-brand-400 rounded-xl transition-all shadow-xs flex items-center">
                            <i data-lucide="log-in" class="w-3.5 h-3.5 mr-1.5 text-brand-600"></i>
                            <span>Log In</span>
                        </button>
                        <button onclick="app.openAuthModal('register')" class="px-3.5 py-1.5 text-xs font-bold text-white bg-brand-600 hover:bg-brand-700 rounded-xl shadow-xs transition-all flex items-center">
                            <i data-lucide="user-plus" class="w-3.5 h-3.5 mr-1.5"></i>
                            <span>Sign Up</span>
                        </button>
                    </div>
                `;
            }
            if (sidebarUserCard) {
                sidebarUserCard.innerHTML = `
                    <div class="text-[11px] font-bold text-slate-700 mb-1 flex items-center">
                        <i data-lucide="user" class="w-3.5 h-3.5 mr-1 text-brand-600"></i> Student Account
                    </div>
                    <p class="text-[10px] text-slate-400 mb-2.5">Sign in to sync your notes and track quiz progress.</p>
                    <div class="grid grid-cols-2 gap-1.5">
                        <button onclick="app.openAuthModal('login')" class="py-1 px-2 text-center text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors">
                            Log In
                        </button>
                        <button onclick="app.openAuthModal('register')" class="py-1 px-2 text-center text-xs font-bold text-white bg-brand-600 hover:bg-brand-700 rounded-lg transition-colors">
                            Sign Up
                        </button>
                    </div>
                `;
            }
        }
        if (window.lucide) lucide.createIcons();
    }

    openAuthModal(tab = "login") {
        this.setAuthTab(tab);
        document.getElementById("authModal").classList.remove("hidden");
    }

    closeAuthModal() {
        document.getElementById("authModal").classList.add("hidden");
    }

    setAuthTab(tab) {
        this.authTab = tab;
        const loginTab = document.getElementById("authTabLogin");
        const regTab = document.getElementById("authTabRegister");
        const userField = document.getElementById("authUsernameField");
        const submitBtn = document.getElementById("authSubmitBtn");
        const title = document.getElementById("authModalTitle");
        const err = document.getElementById("authErrorMessage");
        err.classList.add("hidden");

        if (tab === "login") {
            loginTab.className = "flex-1 py-2 text-brand-600 border-b-2 border-brand-600";
            regTab.className = "flex-1 py-2 text-slate-400 hover:text-slate-600";
            userField.classList.add("hidden");
            submitBtn.textContent = "Sign In";
            title.textContent = "Sign in to your Study Account";
        } else {
            loginTab.className = "flex-1 py-2 text-slate-400 hover:text-slate-600";
            regTab.className = "flex-1 py-2 text-brand-600 border-b-2 border-brand-600";
            userField.classList.remove("hidden");
            submitBtn.textContent = "Create Account";
            title.textContent = "Create a New Student Account";
        }
    }

    async handleAuthSubmit(e) {
        e.preventDefault();
        const err = document.getElementById("authErrorMessage");
        err.classList.add("hidden");

        const email = document.getElementById("authInputEmail").value.trim();
        const password = document.getElementById("authInputPassword").value;
        const username = document.getElementById("authInputUsername").value.trim();

        try {
            let res;
            if (this.authTab === "login") {
                res = await this.api("/api/auth/login", {
                    method: "POST",
                    body: { email, password }
                });
            } else {
                res = await this.api("/api/auth/register", {
                    method: "POST",
                    body: { username, email, password }
                });
            }

            this.token = res.access_token;
            localStorage.setItem("study_token", this.token);
            this.currentUser = res.user;
            this.closeAuthModal();
            this.renderAuthNav();
            this.showToast(`Welcome, ${res.user.username}!`, "success");
            await this.loadCurrentUser();
            await this.loadDocuments();
            await this.loadDashboardStats();
        } catch (error) {
            err.textContent = error.message;
            err.classList.remove("hidden");
        }
    }

    async loginDemoGuest(showNotification = true) {
        try {
            const res = await this.api("/api/auth/login", {
                method: "POST",
                body: { email: "demo@studyaide.com", password: "demo-password-123" }
            }).catch(async () => {
                return await this.api("/api/auth/register", {
                    method: "POST",
                    body: { username: "DemoStudent", email: "demo@studyaide.com", password: "demo-password-123" }
                });
            });

            this.token = res.access_token;
            localStorage.setItem("study_token", this.token);
            this.currentUser = res.user;
            this.closeAuthModal();
            this.renderAuthNav();
            if (showNotification) this.showToast("Signed in as Demo Student!", "success");
            await this.loadCurrentUser();
            await this.loadDocuments();
            await this.loadDashboardStats();
        } catch (e) {
            console.error("Demo login error:", e);
        }
    }

    async logout() {
        try {
            await this.api("/api/auth/logout", { method: "POST" });
        } catch (_) {}
        this.token = null;
        localStorage.removeItem("study_token");
        this.currentUser = null;
        this.renderLoggedOutState();
        this.renderAuthNav();
        this.showToast("You have been logged out.", "info");
        this.openAuthModal('login');
    }

    // ==========================================
    // DOCUMENT MANAGEMENT & UPLOAD
    // ==========================================
    initDropzone() {
        const dropzone = document.getElementById("dropzone");
        if (!dropzone) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => {
                dropzone.classList.add("border-brand-500", "bg-brand-50/20");
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => {
                dropzone.classList.remove("border-brand-500", "bg-brand-50/20");
            }, false);
        });

        dropzone.addEventListener("drop", (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.uploadFile(files[0]);
            }
        });

        dropzone.addEventListener("click", () => {
            const fileInput = document.getElementById("pdfFileInput");
            if (fileInput) fileInput.click();
        });
    }

    handleFileSelect(e) {
        if (e.target.files && e.target.files.length > 0) {
            this.uploadFile(e.target.files[0]);
        }
    }

    async uploadFile(file) {
        if (!this.currentUser) {
            this.showToast("Please log in or sign up to upload documents.", "error");
            this.openAuthModal('login');
            return;
        }

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            this.showToast("Please select a PDF file (.pdf).", "error");
            return;
        }

        const progress = document.getElementById("uploadProgressContainer");
        const statusText = document.getElementById("uploadStatusText");
        if (progress) progress.classList.remove("hidden");
        if (statusText) statusText.textContent = `Analyzing ${file.name}...`;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await this.api("/api/documents/upload", {
                method: "POST",
                body: formData,
                isFormData: true
            });

            this.showToast(`Uploaded "${res.document.title}" successfully!`, "success");
            await this.loadDocuments();
            this.switchActiveDocument(res.document.id);
        } catch (err) {
            this.showToast(err.message, "error");
        } finally {
            if (progress) progress.classList.add("hidden");
            const fileInput = document.getElementById("pdfFileInput");
            if (fileInput) fileInput.value = "";
        }
    }

    async loadSampleNotes() {
        if (!this.currentUser) {
            this.showToast("Please log in or sign up first.", "info");
            this.openAuthModal('login');
            return;
        }
        this.showToast("Loading comprehensive CS101 study notes...", "info");
        try {
            const res = await this.api("/api/documents/load-sample", { method: "POST" });
            this.showToast("Sample study material ready!", "success");
            await this.loadDocuments();
            this.switchActiveDocument(res.doc_id);
        } catch (err) {
            this.showToast(err.message, "error");
        }
    }

    async loadDocuments() {
        try {
            this.documents = await this.api("/api/documents");
            this.renderDocumentSelectors();
            this.renderDocumentLibrary();
            this.renderDashboardRecentDocs();

            // Auto select first document if none active
            if (!this.activeDocId && this.documents.length > 0) {
                this.switchActiveDocument(this.documents[0].id);
            } else if (this.activeDocId) {
                this.updateActiveDocDisplay();
            }
        } catch (err) {
            console.error("Error loading documents:", err);
        }
    }

    renderDocumentSelectors() {
        const select = document.getElementById("activeDocSelect");
        if (!select) return;

        select.innerHTML = "";
        if (this.documents.length === 0) {
            select.innerHTML = '<option value="">No documents uploaded</option>';
            return;
        }

        this.documents.forEach(doc => {
            const opt = document.createElement("option");
            opt.value = doc.id;
            opt.textContent = `${doc.title} (${doc.page_count}p)`;
            if (doc.id === this.activeDocId) opt.selected = true;
            select.appendChild(opt);
        });
    }

    renderDocumentLibrary() {
        const container = document.getElementById("docLibraryList");
        const countBadge = document.getElementById("docCountBadge");
        const sidebarBadge = document.getElementById("sidebarDocBadge");

        if (countBadge) countBadge.textContent = `${this.documents.length} document${this.documents.length === 1 ? '' : 's'}`;
        if (sidebarBadge) sidebarBadge.textContent = this.documents.length;
        if (!container) return;

        if (this.documents.length === 0) {
            container.innerHTML = `
                <div class="py-12 text-center text-slate-400">
                    <i data-lucide="folder-open" class="w-10 h-10 mx-auto mb-2 text-slate-300"></i>
                    <p class="text-sm font-semibold text-slate-600">No documents uploaded yet</p>
                    <p class="text-xs text-slate-400 mt-1">Upload a PDF above or click 'Add Sample AI Lecture Notes'.</p>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        container.innerHTML = this.documents.map(doc => {
            const isActive = doc.id === this.activeDocId;
            const fileSizeKb = Math.round(doc.file_size / 1024);
            const readMins = Math.max(1, Math.round((doc.word_count || 500) / 200));

            return `
                <div class="p-4 hover:bg-slate-50/80 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${isActive ? 'bg-brand-50/40' : ''}">
                    <div class="flex items-start space-x-3 min-w-0">
                        <div class="p-2.5 rounded-xl ${isActive ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600'} flex-shrink-0">
                            <i data-lucide="file-text" class="w-5 h-5"></i>
                        </div>
                        <div class="min-w-0">
                            <div class="flex items-center space-x-2">
                                <h4 class="text-sm font-bold text-slate-900 truncate">${doc.title}</h4>
                                ${isActive ? '<span class="text-[10px] font-bold uppercase tracking-wider bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">Active</span>' : ''}
                            </div>
                            <div class="flex items-center space-x-3 text-xs text-slate-500 mt-1">
                                <span><i data-lucide="book-open" class="w-3.5 h-3.5 inline mr-1 text-slate-400"></i>${doc.page_count} Pages</span>
                                <span>•</span>
                                <span><i data-lucide="clock" class="w-3.5 h-3.5 inline mr-1 text-slate-400"></i>~${readMins} min read</span>
                                <span>•</span>
                                <span>${fileSizeKb} KB</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center space-x-2 self-end sm:self-center">
                        <button onclick="app.convertDocToQuiz(${doc.id})" class="px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-purple-700 text-xs font-bold rounded-lg transition-colors flex items-center shadow-2xs" title="Convert PDF into Quiz">
                            <i data-lucide="sparkles" class="w-3.5 h-3.5 mr-1 text-purple-600"></i> Quiz
                        </button>
                        ${!isActive ? `
                            <button onclick="app.switchActiveDocument(${doc.id})" class="px-3 py-1.5 bg-brand-50 hover:bg-brand-100 text-brand-700 text-xs font-semibold rounded-lg transition-colors">
                                Select
                            </button>
                        ` : ''}
                        <button onclick="app.openReaderModal(${doc.id})" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition-colors flex items-center">
                            <i data-lucide="eye" class="w-3.5 h-3.5 mr-1"></i> Read Text
                        </button>
                        <button onclick="app.deleteDocument(${doc.id})" class="p-1.5 text-slate-400 hover:text-red-600 rounded-lg transition-colors" title="Delete Document">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join("");

        if (window.lucide) lucide.createIcons();
    }

    renderDashboardRecentDocs() {
        const list = document.getElementById("dashRecentDocsList");
        if (!list) return;

        if (this.documents.length === 0) {
            list.innerHTML = `
                <div class="py-6 text-center text-slate-400 text-xs">
                    No study documents added yet.
                </div>
            `;
            return;
        }

        list.innerHTML = this.documents.slice(0, 4).map(doc => {
            const isActive = doc.id === this.activeDocId;
            return `
                <div class="py-3 flex items-center justify-between">
                    <div class="flex items-center space-x-3 min-w-0">
                        <div class="p-2 rounded-lg ${isActive ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-slate-500'}">
                            <i data-lucide="file" class="w-4 h-4"></i>
                        </div>
                        <div class="min-w-0">
                            <p class="text-xs font-bold text-slate-800 truncate">${doc.title}</p>
                            <p class="text-[11px] text-slate-400">${doc.page_count} pages • Uploaded ${doc.created_at || 'recently'}</p>
                        </div>
                    </div>
                    <button onclick="app.switchActiveDocument(${doc.id})" class="text-xs font-semibold ${isActive ? 'text-brand-600' : 'text-slate-500 hover:text-brand-600'}">
                        ${isActive ? 'Active' : 'Study This'}
                    </button>
                </div>
            `;
        }).join("");

        if (window.lucide) lucide.createIcons();
    }

    async switchActiveDocument(docId) {
        if (!docId) return;
        this.activeDocId = parseInt(docId);
        this.activeDoc = this.documents.find(d => d.id === this.activeDocId);

        // Update selector
        const select = document.getElementById("activeDocSelect");
        if (select) select.value = this.activeDocId;

        this.updateActiveDocDisplay();
        this.renderDocumentLibrary();
        this.renderDashboardRecentDocs();

        // Refresh views for the newly selected document
        if (this.activeView === "chat") {
            await this.loadChatHistory();
        }
    }

    updateActiveDocDisplay() {
        if (!this.activeDoc) return;
        const sidebarTitle = document.getElementById("sidebarActiveDocTitle");
        const sidebarMeta = document.getElementById("sidebarActiveDocMeta");
        const chatPill = document.getElementById("chatDocTitlePill");
        const quizLabel = document.getElementById("quizSourceDocLabel");

        if (sidebarTitle) sidebarTitle.textContent = this.activeDoc.title;
        if (sidebarMeta) sidebarMeta.textContent = `${this.activeDoc.page_count} Pages • ${Math.round(this.activeDoc.file_size / 1024)} KB`;
        if (chatPill) chatPill.textContent = this.activeDoc.title;
        if (quizLabel) quizLabel.textContent = `PDF: ${this.activeDoc.title} (${this.activeDoc.page_count}p)`;
    }

    async convertDocToQuiz(docId) {
        if (!docId) return;
        await this.switchActiveDocument(docId);
        this.navigate("quiz");
        const label = document.getElementById("quizSourceDocLabel");
        if (label && this.activeDoc) {
            label.textContent = `PDF: ${this.activeDoc.title} (${this.activeDoc.page_count}p)`;
        }
        this.showToast(`Selected "${this.activeDoc?.title || 'document'}" for Quiz conversion. Choose options and click 'Convert PDF into Quiz Now'!`, "info");
    }

    async deleteDocument(docId) {
        if (!confirm("Are you sure you want to delete this study document and its chat history?")) return;
        try {
            await this.api(`/api/documents/${docId}`, { method: "DELETE" });
            this.showToast("Document deleted.", "info");
            if (this.activeDocId === docId) {
                this.activeDocId = null;
                this.activeDoc = null;
            }
            await this.loadDocuments();
        } catch (err) {
            this.showToast(err.message, "error");
        }
    }

    async openReaderModal(docId) {
        try {
            const doc = await this.api(`/api/documents/${docId}`);
            document.getElementById("readerDocTitle").textContent = doc.title;
            document.getElementById("readerDocMeta").textContent = `${doc.page_count} Pages • ${doc.word_count} total words extracted`;

            const container = document.getElementById("readerPagesContainer");
            container.innerHTML = doc.extracted_pages.map(page => `
                <div class="p-4 rounded-xl bg-slate-50 border border-slate-200">
                    <div class="text-[11px] font-bold uppercase tracking-wider text-brand-600 mb-2 flex items-center justify-between">
                        <span>Page ${page.page}</span>
                        <span class="text-slate-400 font-normal">${page.word_count} words</span>
                    </div>
                    <div class="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap font-sans">
                        ${page.text || '<span class="italic text-slate-400">No text detected on this page.</span>'}
                    </div>
                </div>
            `).join("");

            document.getElementById("readerModal").classList.remove("hidden");
        } catch (err) {
            this.showToast(err.message, "error");
        }
    }

    closeReaderModal() {
        document.getElementById("readerModal").classList.add("hidden");
    }

    // ==========================================
    // AI NOTES SUMMARIZER
    // ==========================================
    async generateSummary(forceRefresh = true) {
        if (!this.activeDocId) {
            this.showToast("Please select or upload a document first.", "error");
            this.navigate("documents");
            return;
        }

        const length = document.getElementById("summaryLengthSelect").value;
        const formatStyle = document.getElementById("summaryFormatSelect").value;
        const spinner = document.getElementById("summaryLoadingSpinner");
        const contentDiv = document.getElementById("summaryContent");

        if (spinner) spinner.classList.remove("hidden");

        try {
            const res = await this.api(`/api/summarize/${this.activeDocId}`, {
                method: "POST",
                body: { length, format_style: formatStyle, force_refresh: forceRefresh }
            });

            this.currentSummary = res.summary;
            if (contentDiv) {
                contentDiv.innerHTML = marked.parse(res.summary);
            }
            this.showToast(res.cached ? "Loaded summary from cache." : "Generated fresh AI summary!", "success");
        } catch (err) {
            this.showToast(err.message, "error");
        } finally {
            if (spinner) spinner.classList.add("hidden");
        }
    }

    copySummaryToClipboard() {
        if (!this.currentSummary) {
            this.showToast("No summary to copy.", "error");
            return;
        }
        navigator.clipboard.writeText(this.currentSummary);
        this.showToast("Summary copied to clipboard!", "success");
    }

    async saveCurrentSummaryAsNote() {
        if (!this.currentSummary || !this.activeDoc) {
            this.showToast("Generate a summary before saving.", "error");
            return;
        }

        try {
            await this.api(`/api/summarize/${this.activeDocId}/save-revision-note`, {
                method: "POST",
                body: {
                    title: `Summary: ${this.activeDoc.title}`,
                    content: this.currentSummary,
                    note_type: "summary"
                }
            });

            this.showToast("Saved to your Revision Notes!", "success");
            await this.loadDashboardStats();
        } catch (err) {
            this.showToast(err.message, "error");
        }
    }

    // ==========================================
    // AI STUDY CHATBOT
    // ==========================================
    async loadChatHistory() {
        if (!this.activeDocId) return;
        try {
            const history = await this.api(`/api/chat/${this.activeDocId}/history`);
            this.renderChatMessages(history);
        } catch (err) {
            console.error("Error loading chat:", err);
        }
    }

    renderChatMessages(messages) {
        const stream = document.getElementById("chatMessagesStream");
        if (!stream) return;

        if (messages.length === 0) {
            stream.innerHTML = `
                <div class="p-4 rounded-xl bg-slate-50 border border-slate-200 text-slate-600 text-xs">
                    <div class="font-bold text-slate-800 mb-1 flex items-center">
                        <i data-lucide="bot" class="w-4 h-4 mr-1.5 text-brand-600"></i> AI Study Tutor Online
                    </div>
                    Ask questions about formulas, definitions, algorithms, or theories from <b>${this.activeDoc ? this.activeDoc.title : 'your notes'}</b>.
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        stream.innerHTML = messages.map(msg => {
            const isUser = msg.role === "user";
            let citationsHtml = "";

            if (!isUser && msg.citations && msg.citations.length > 0) {
                citationsHtml = `
                    <div class="mt-3 pt-2.5 border-t border-slate-200/80">
                        <div class="text-[10px] font-bold uppercase tracking-wider text-brand-600 mb-1.5 flex items-center">
                            <i data-lucide="bookmark" class="w-3 h-3 mr-1"></i> Document Citations
                        </div>
                        <div class="flex flex-wrap gap-1.5">
                            ${msg.citations.map(c => `
                                <span class="inline-flex items-center text-[11px] font-medium px-2 py-0.5 rounded-md bg-white border border-brand-200 text-brand-800 shadow-2xs" title="${c.snippet}">
                                    <i data-lucide="file-text" class="w-3 h-3 mr-1 text-brand-500"></i> Page ${c.page}
                                </span>
                            `).join("")}
                        </div>
                    </div>
                `;
            }

            return `
                <div class="flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}">
                    <div class="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-bold ${isUser ? 'bg-brand-600 text-white' : 'bg-indigo-600 text-white'}">
                        ${isUser ? 'You' : '<i data-lucide="bot" class="w-4 h-4"></i>'}
                    </div>
                    <div class="max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed ${isUser ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-800'}">
                        <div class="markdown-body ${isUser ? 'text-white' : ''}">
                            ${marked.parse(msg.content)}
                        </div>
                        ${citationsHtml}
                    </div>
                </div>
            `;
        }).join("");

        if (window.lucide) lucide.createIcons();
        stream.scrollTop = stream.scrollHeight;
    }

    handleChatKeydown(e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            this.handleChatSubmit(e);
        }
    }

    askSuggested(query) {
        const input = document.getElementById("chatInputText");
        if (input) {
            input.value = query;
            this.handleChatSubmit(new Event('submit'));
        }
    }

    async handleChatSubmit(e) {
        e.preventDefault();
        const input = document.getElementById("chatInputText");
        const query = input.value.trim();
        if (!query) return;

        if (!this.activeDocId) {
            this.showToast("Please upload or select a document first.", "error");
            return;
        }

        input.value = "";
        const stream = document.getElementById("chatMessagesStream");

        // Append user temporary bubble
        const userBubble = document.createElement("div");
        userBubble.className = "flex items-start space-x-3 flex-row-reverse space-x-reverse";
        userBubble.innerHTML = `
            <div class="w-7 h-7 rounded-lg bg-brand-600 text-white flex items-center justify-center flex-shrink-0 text-xs font-bold">You</div>
            <div class="max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed bg-brand-600 text-white">${query}</div>
        `;
        stream.appendChild(userBubble);

        // Loading bubble
        const loadingBubble = document.createElement("div");
        loadingBubble.id = "chatLoadingBubble";
        loadingBubble.className = "flex items-start space-x-3";
        loadingBubble.innerHTML = `
            <div class="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center flex-shrink-0">
                <i data-lucide="bot" class="w-4 h-4"></i>
            </div>
            <div class="p-3.5 bg-slate-100 rounded-2xl text-xs text-slate-500 flex items-center space-x-2">
                <div class="w-3 h-3 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
                <span>Searching document pages for answers...</span>
            </div>
        `;
        stream.appendChild(loadingBubble);
        stream.scrollTop = stream.scrollHeight;
        if (window.lucide) lucide.createIcons();

        try {
            await this.api(`/api/chat/${this.activeDocId}`, {
                method: "POST",
                body: { message: query }
            });
            await this.loadChatHistory();
        } catch (err) {
            loadingBubble.remove();
            this.showToast(err.message, "error");
        }
    }

    async clearChatHistory() {
        if (!this.activeDocId) return;
        if (!confirm("Clear conversation history for this document?")) return;
        try {
            await this.api(`/api/chat/${this.activeDocId}/history`, { method: "DELETE" });
            await this.loadChatHistory();
            this.showToast("Chat history cleared.", "info");
        } catch (err) {
            this.showToast(err.message, "error");
        }
    }

    // ==========================================
    // QUIZZES & FLASHCARDS
    // ==========================================
    setQuizMode(mode) {
        this.quizMode = mode;
        const btnMcq = document.getElementById("btnQuizModeMcq");
        const btnTf = document.getElementById("btnQuizModeTf");
        const btnFlash = document.getElementById("btnQuizModeFlashcards");
        const mcqBox = document.getElementById("quizContainerMcq");
        const flashBox = document.getElementById("quizContainerFlashcards");

        [btnMcq, btnTf, btnFlash].forEach(btn => {
            if (btn) btn.className = "px-3.5 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition-all font-semibold";
        });

        if (mode === "mcq") {
            if (btnMcq) btnMcq.className = "px-3.5 py-1.5 rounded-lg bg-white text-purple-700 shadow-xs font-bold transition-all";
            if (mcqBox) mcqBox.classList.remove("hidden");
            if (flashBox) flashBox.classList.add("hidden");
        } else if (mode === "true_false") {
            if (btnTf) btnTf.className = "px-3.5 py-1.5 rounded-lg bg-white text-purple-700 shadow-xs font-bold transition-all";
            if (mcqBox) mcqBox.classList.remove("hidden");
            if (flashBox) flashBox.classList.add("hidden");
        } else {
            if (btnFlash) btnFlash.className = "px-3.5 py-1.5 rounded-lg bg-white text-purple-700 shadow-xs font-bold transition-all";
            if (flashBox) flashBox.classList.remove("hidden");
            if (mcqBox) mcqBox.classList.add("hidden");
        }
    }

    async convertActivePdfToQuiz() {
        if (!this.activeDocId) {
            this.showToast("Please upload or select a study document first.", "error");
            this.navigate("documents");
            return;
        }

        const countSelect = document.getElementById("quizCountSelect");
        const diffSelect = document.getElementById("quizDifficultySelect");
        const count = countSelect ? parseInt(countSelect.value || 5) : 5;
        const difficulty = diffSelect ? diffSelect.value : "medium";
        const mode = this.quizMode || "mcq";

        const btn = document.getElementById("btnGenerateQuiz");
        const originalText = btn ? btn.innerHTML : "";
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<div class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div> Converting PDF with Gemini 3.8 Flash...`;
        }

        const mcqBox = document.getElementById("quizContainerMcq");
        const flashBox = document.getElementById("quizContainerFlashcards");

        if (mode === "flashcards") {
            if (flashBox) {
                flashBox.classList.remove("hidden");
                const front = document.getElementById("cardFrontText");
                const back = document.getElementById("cardBackText");
                if (front) front.textContent = "Synthesizing flashcards with Gemini 3.8 Flash...";
                if (back) back.textContent = "Please wait a moment...";
            }
        } else {
            if (mcqBox) {
                mcqBox.classList.remove("hidden");
                mcqBox.innerHTML = `
                    <div class="bg-white p-10 text-center rounded-xl border border-purple-200 shadow-xs">
                        <div class="w-10 h-10 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-3"></div>
                        <p class="text-sm font-bold text-slate-800">Converting "${this.activeDoc ? this.activeDoc.title : 'PDF'}" into Quiz...</p>
                        <p class="text-xs text-slate-500 mt-1">Generating ${count} ${difficulty} ${mode === 'true_false' ? 'True/False statements' : 'exam questions'} with verified page citations via Gemini 3.8 Flash.</p>
                    </div>
                `;
            }
        }

        try {
            const res = await this.api(`/api/quiz/${this.activeDocId}/convert-pdf`, {
                method: "POST",
                body: {
                    quiz_type: mode,
                    count: count,
                    difficulty: difficulty
                }
            });

            if (mode === "flashcards") {
                this.flashcards = res.items;
                this.flashcardIndex = 0;
                this.renderActiveFlashcard();
            } else {
                this.currentQuiz = res;
                this.quizSelectedAnswers = {};
                this.quizSubmitted = false;
                this.renderMcqQuiz();
            }

            const itemTypeLabel = mode === "flashcards" ? "3D flashcards" : (mode === "true_false" ? "True/False questions" : "MCQ quiz questions");
            this.showToast(`Converted "${this.activeDoc ? this.activeDoc.title : 'PDF'}" into ${res.items.length} ${itemTypeLabel}!`, "success");
        } catch (err) {
            this.showToast(err.message, "error");
            if (mcqBox && mode !== "flashcards") {
                mcqBox.innerHTML = `
                    <div class="bg-white p-8 text-center rounded-xl border border-red-200 text-slate-600">
                        <i data-lucide="alert-circle" class="w-8 h-8 mx-auto mb-2 text-red-500"></i>
                        <p class="text-sm font-bold text-slate-800">Quiz Generation Notice</p>
                        <p class="text-xs text-red-600 mt-1">${err.message}</p>
                        <button onclick="app.convertActivePdfToQuiz()" class="mt-4 px-4 py-2 bg-purple-600 text-white font-bold text-xs rounded-lg">Retry Conversion</button>
                    </div>
                `;
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalText || `<i data-lucide="sparkles" class="w-4 h-4 mr-2"></i> Convert PDF into Quiz Now`;
            }
            if (window.lucide) lucide.createIcons();
        }
    }

    async generateNewQuiz() {
        return this.convertActivePdfToQuiz();
    }

    renderMcqQuiz() {
        const container = document.getElementById("quizContainerMcq");
        if (!container || !this.currentQuiz) return;

        const questions = this.currentQuiz.items;

        container.innerHTML = `
            <div class="space-y-4">
                ${questions.map((q, idx) => `
                    <div id="quizQuestionCard_${q.id}" class="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
                        <div class="flex items-center justify-between mb-3">
                            <span class="text-xs font-bold text-brand-600 uppercase tracking-wider">Question ${idx + 1} of ${questions.length}</span>
                            <span class="text-[11px] text-slate-400 font-semibold bg-slate-100 px-2 py-0.5 rounded-full">Source: Page ${q.page || 1}</span>
                        </div>
                        <h3 class="text-sm font-bold text-slate-900 mb-4">${q.question}</h3>

                        <div class="grid grid-cols-1 gap-2.5">
                            ${q.options.map((opt, optIdx) => {
                                const letter = ["A", "B", "C", "D"][optIdx];
                                const isSelected = this.quizSelectedAnswers[q.id] === letter;
                                return `
                                    <button 
                                        type="button"
                                        id="optBtn_${q.id}_${letter}"
                                        onclick="app.selectQuizOption(${q.id}, '${letter}')" 
                                        class="quiz-opt-btn w-full text-left p-3 rounded-lg border text-xs font-medium transition-all flex items-center justify-between ${isSelected ? 'border-brand-500 bg-brand-50/70 text-brand-900 font-bold' : 'border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700'}"
                                    >
                                        <div class="flex items-center space-x-3">
                                            <span class="w-6 h-6 rounded-md bg-white border border-slate-200 flex items-center justify-center font-bold text-xs text-slate-600 shadow-2xs">${letter}</span>
                                            <span>${opt}</span>
                                        </div>
                                        <span id="optBadge_${q.id}_${letter}"></span>
                                    </button>
                                `;
                            }).join("")}
                        </div>

                        <!-- Feedback Box (Hidden until submitted) -->
                        <div id="quizFeedback_${q.id}" class="hidden mt-4 p-3 rounded-lg text-xs leading-relaxed"></div>
                    </div>
                `).join("")}

                <!-- Submit Button Bar -->
                <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
                    <span id="quizAnsweredCount" class="text-xs font-semibold text-slate-600">0 of ${questions.length} answered</span>
                    <button onclick="app.submitQuiz()" id="btnSubmitQuiz" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg transition-all shadow-xs flex items-center">
                        <i data-lucide="check-circle" class="w-4 h-4 mr-1.5"></i> Submit & Grade Quiz
                    </button>
                </div>
            </div>
        `;

        if (window.lucide) lucide.createIcons();
    }

    selectQuizOption(questionId, letter) {
        if (this.quizSubmitted) return;
        this.quizSelectedAnswers[questionId] = letter;

        // Update button visual state
        ["A", "B", "C", "D"].forEach(l => {
            const btn = document.getElementById(`optBtn_${questionId}_${l}`);
            if (btn) {
                if (l === letter) {
                    btn.className = "quiz-opt-btn w-full text-left p-3 rounded-lg border border-brand-500 bg-brand-50/70 text-brand-900 font-bold text-xs flex items-center justify-between shadow-xs";
                } else {
                    btn.className = "quiz-opt-btn w-full text-left p-3 rounded-lg border border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-700 text-xs flex items-center justify-between";
                }
            }
        });

        const answered = Object.keys(this.quizSelectedAnswers).length;
        const countEl = document.getElementById("quizAnsweredCount");
        if (countEl) countEl.textContent = `${answered} of ${this.currentQuiz.items.length} answered`;
    }

    async submitQuiz() {
        if (!this.currentQuiz) return;
        const total = this.currentQuiz.items.length;
        const answered = Object.keys(this.quizSelectedAnswers).length;

        if (answered < total) {
            if (!confirm(`You have only answered ${answered} of ${total} questions. Submit anyway?`)) return;
        }

        try {
            const res = await this.api(`/api/quiz/${this.currentQuiz.quiz_id}/submit`, {
                method: "POST",
                body: { answers: this.quizSelectedAnswers }
            });

            this.quizSubmitted = true;
            this.showQuizResults(res);
            await this.loadDashboardStats();
        } catch (err) {
            this.showToast(err.message, "error");
        }
    }

    showQuizResults(res) {
        // Highlight correct and incorrect options
        res.results.forEach(item => {
            const qid = item.question_id;
            const feedbackBox = document.getElementById(`quizFeedback_${qid}`);

            ["A", "B", "C", "D"].forEach(l => {
                const btn = document.getElementById(`optBtn_${qid}_${l}`);
                const badge = document.getElementById(`optBadge_${qid}_${l}`);
                if (!btn) return;

                if (l === item.correct_answer) {
                    btn.className = "quiz-opt-btn w-full text-left p-3 rounded-lg border border-emerald-500 bg-emerald-50 text-emerald-900 font-bold text-xs flex items-center justify-between";
                    if (badge) badge.innerHTML = `<span class="text-emerald-700 font-bold text-xs">✓ Correct</span>`;
                } else if (l === item.user_answer && !item.is_correct) {
                    btn.className = "quiz-opt-btn w-full text-left p-3 rounded-lg border border-red-500 bg-red-50 text-red-900 font-bold text-xs flex items-center justify-between";
                    if (badge) badge.innerHTML = `<span class="text-red-700 font-bold text-xs">✗ Your choice</span>`;
                } else {
                    btn.className = "quiz-opt-btn w-full text-left p-3 rounded-lg border border-slate-200 bg-slate-50/30 text-slate-400 text-xs flex items-center justify-between opacity-60";
                }
            });

            if (feedbackBox) {
                feedbackBox.classList.remove("hidden");
                feedbackBox.className = `mt-4 p-3 rounded-lg text-xs leading-relaxed ${item.is_correct ? 'bg-emerald-50/80 border border-emerald-200 text-emerald-900' : 'bg-amber-50/80 border border-amber-200 text-amber-900'}`;
                feedbackBox.innerHTML = `
                    <div class="font-bold mb-1 flex items-center">
                        <i data-lucide="${item.is_correct ? 'check-circle' : 'info'}" class="w-3.5 h-3.5 mr-1 text-${item.is_correct ? 'emerald' : 'amber'}-600"></i>
                        ${item.is_correct ? 'Great Job!' : 'Review Concept'}
                    </div>
                    <div>${item.explanation}</div>
                `;
            }
        });

        // Hide submit button and show score card
        const btnSubmit = document.getElementById("btnSubmitQuiz");
        if (btnSubmit) {
            btnSubmit.parentElement.innerHTML = `
                <div class="w-full flex flex-col sm:flex-row items-center justify-between gap-3">
                    <div class="flex items-center space-x-3">
                        <div class="w-12 h-12 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center font-extrabold text-base">
                            ${res.percentage}%
                        </div>
                        <div>
                            <h4 class="text-sm font-bold text-slate-900">Quiz Completed! Score: ${res.score} / ${res.total}</h4>
                            <p class="text-xs text-slate-500">${res.percentage >= 80 ? 'Mastery demonstrated! Outstanding recall.' : res.percentage >= 50 ? 'Good effort! Review the highlighted pages above.' : 'Needs revision. Review notes and retry.'}</p>
                        </div>
                    </div>
                    <button onclick="app.generateNewQuiz()" class="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-lg transition-all shadow-xs">
                        Try Another Quiz
                    </button>
                </div>
            `;
        }

        if (window.lucide) lucide.createIcons();
    }

    // Flashcards
    renderActiveFlashcard() {
        if (!this.flashcards || this.flashcards.length === 0) return;
        const card = this.flashcards[this.flashcardIndex];

        const front = document.getElementById("cardFrontText");
        const back = document.getElementById("cardBackText");
        const pageBadge = document.getElementById("cardPageBadge");
        const counter = document.getElementById("flashcardCounter");
        const cardInner = document.getElementById("activeFlashcard");

        if (cardInner) cardInner.classList.remove("flipped");
        if (front) front.textContent = card.front;
        if (back) back.textContent = card.back;
        if (pageBadge) pageBadge.textContent = `Page ${card.page || 1}`;
        if (counter) counter.textContent = `Card ${this.flashcardIndex + 1} of ${this.flashcards.length}`;
    }

    flipFlashcard() {
        const cardInner = document.getElementById("activeFlashcard");
        if (cardInner) cardInner.classList.toggle("flipped");
    }

    nextFlashcard() {
        if (this.flashcards.length === 0) return;
        this.flashcardIndex = (this.flashcardIndex + 1) % this.flashcards.length;
        this.renderActiveFlashcard();
    }

    prevFlashcard() {
        if (this.flashcards.length === 0) return;
        this.flashcardIndex = (this.flashcardIndex - 1 + this.flashcards.length) % this.flashcards.length;
        this.renderActiveFlashcard();
    }

    // ==========================================
    // REVISION NOTES & BOOKMARKS
    // ==========================================
    async loadSavedNotes() {
        try {
            this.savedNotes = await this.api("/api/notes");
            this.renderSavedNotes();
        } catch (err) {
            console.error("Error loading notes:", err);
        }
    }

    renderSavedNotes() {
        const grid = document.getElementById("savedNotesGrid");
        if (!grid) return;

        if (this.savedNotes.length === 0) {
            grid.innerHTML = `
                <div class="col-span-2 py-12 text-center text-slate-400">
                    <i data-lucide="bookmark" class="w-10 h-10 mx-auto mb-2 text-slate-300"></i>
                    <p class="text-sm font-semibold text-slate-600">No revision notes saved yet</p>
                    <p class="text-xs text-slate-400 mt-1">Generate a summary and click 'Save to Revision Notes', or click 'New Custom Note'.</p>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        grid.innerHTML = this.savedNotes.map(n => `
            <div class="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-[10px] font-bold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-md">${n.note_type}</span>
                        <button onclick="app.deleteNote(${n.id})" class="text-slate-400 hover:text-red-600 p-1 rounded-md" title="Delete Note">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                    <h3 class="text-sm font-bold text-slate-900 mb-2">${n.title}</h3>
                    <div class="text-xs text-slate-600 line-clamp-4 leading-relaxed font-sans prose prose-slate">
                        ${marked.parse(n.content)}
                    </div>
                </div>
                <div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                    <span>${n.doc_title || 'General'}</span>
                    <span>${n.created_at || ''}</span>
                </div>
            </div>
        `).join("");

        if (window.lucide) lucide.createIcons();
    }

    openNewNoteModal() {
        document.getElementById("newNoteModal").classList.remove("hidden");
    }

    closeNewNoteModal() {
        document.getElementById("newNoteModal").classList.add("hidden");
    }

    async handleNewNoteSubmit(e) {
        e.preventDefault();
        const title = document.getElementById("newNoteTitle").value.trim();
        const content = document.getElementById("newNoteContent").value.trim();
        if (!title || !content) return;

        try {
            await this.api("/api/notes", {
                method: "POST",
                body: {
                    document_id: this.activeDocId,
                    title: title,
                    content: content,
                    note_type: "custom"
                }
            });
            this.closeNewNoteModal();
            this.showToast("Note created successfully!", "success");
            await this.loadSavedNotes();
            await this.loadDashboardStats();
        } catch (err) {
            this.showToast(err.message, "error");
        }
    }

    async deleteNote(noteId) {
        if (!confirm("Delete this revision note?")) return;
        try {
            await this.api(`/api/notes/${noteId}`, { method: "DELETE" });
            this.showToast("Note deleted.", "info");
            await this.loadSavedNotes();
            await this.loadDashboardStats();
        } catch (err) {
            this.showToast(err.message, "error");
        }
    }

    // ==========================================
    // SETTINGS & AI CONFIGURATION
    // ==========================================
    openSettingsModal() {
        const defaultGemini = "";
        const providerSelect = document.getElementById("settingsAiProvider");
        const geminiInput = document.getElementById("settingsGeminiKey");

        if (this.currentUser) {
            if (providerSelect) providerSelect.value = this.currentUser.ai_provider || "gemini";
            if (geminiInput) geminiInput.value = this.currentUser.gemini_api_key || "";
        } else {
            if (providerSelect) providerSelect.value = "gemini";
            if (geminiInput) geminiInput.value = "";
        }
        this.toggleSettingsKeyFields();
        document.getElementById("settingsModal").classList.remove("hidden");
    }

    closeSettingsModal() {
        document.getElementById("settingsModal").classList.add("hidden");
    }

    toggleSettingsKeyFields() {
        const val = document.getElementById("settingsAiProvider").value;
        const geminiGroup = document.getElementById("settingsGeminiGroup");
        const openAiGroup = document.getElementById("settingsOpenAiGroup");

        if (val === "gemini") {
            geminiGroup.classList.remove("hidden");
            openAiGroup.classList.add("hidden");
        } else if (val === "openai") {
            openAiGroup.classList.remove("hidden");
            geminiGroup.classList.add("hidden");
        } else {
            geminiGroup.classList.add("hidden");
            openAiGroup.classList.add("hidden");
        }
    }

    async handleSettingsSubmit(e) {
        e.preventDefault();
        const provider = document.getElementById("settingsAiProvider").value;
        const geminiKey = document.getElementById("settingsGeminiKey").value.trim();
        const openAiKey = document.getElementById("settingsOpenAiKey").value.trim();

        try {
            await this.api("/api/auth/settings/ai", {
                method: "POST",
                body: {
                    ai_provider: provider,
                    gemini_api_key: geminiKey,
                    openai_api_key: openAiKey
                }
            });
            if (this.currentUser) this.currentUser.ai_provider = provider;
            this.closeSettingsModal();
            this.renderAuthNav();
            this.showToast("AI preferences saved!", "success");
        } catch (err) {
            this.showToast(err.message, "error");
        }
    }

    // ==========================================
    // NAVIGATION & ROUTING
    // ==========================================
    navigate(view) {
        this.activeView = view;
        const views = ["dashboard", "documents", "summary", "chat", "quiz", "notes"];

        views.forEach(v => {
            const sec = document.getElementById(`view-${v}`);
            const nav = document.getElementById(`nav-${v}`);
            if (sec) {
                if (v === view) {
                    sec.classList.remove("hidden");
                } else {
                    sec.classList.add("hidden");
                }
            }
            if (nav) {
                if (v === view) {
                    nav.className = "nav-tab w-full flex items-center space-x-3 px-3.5 py-2.5 text-sm font-semibold rounded-xl transition-all duration-150 text-brand-700 bg-brand-50 border border-brand-200";
                } else {
                    nav.className = "nav-tab w-full flex items-center space-x-3 px-3.5 py-2.5 text-sm font-medium rounded-xl transition-all duration-150 text-slate-600 hover:text-slate-900 hover:bg-slate-100";
                }
            }
        });

        // Trigger view-specific data loads
        if (view === "chat") {
            this.loadChatHistory();
        } else if (view === "notes") {
            this.loadSavedNotes();
        } else if (view === "dashboard") {
            this.loadDashboardStats();
        }

        if (window.lucide) lucide.createIcons();
    }

    quickAction(action) {
        if (!this.currentUser) {
            this.showToast("Please log in or sign up to access study tools.", "info");
            this.openAuthModal('login');
            return;
        }
        if (!this.activeDocId && this.documents.length === 0) {
            this.loadSampleNotes().then(() => this.navigate(action));
            return;
        }
        this.navigate(action);
    }

    async loadDashboardStats() {
        if (this.currentUser) {
            await this.loadCurrentUser();
        }
    }
}

// Global App Instance
const app = new StudyApp();
document.addEventListener("DOMContentLoaded", () => {
    app.init();
});
