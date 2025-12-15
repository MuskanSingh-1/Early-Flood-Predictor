(() => {
  "use strict";

  /*Configuration*/
  const BACKEND = "https://early-flood-predictor.onrender.com";
  const AUTH_LOGIN = `${BACKEND}/auth/login`;
  const AUTH_SIGNUP = `${BACKEND}/auth/signup`;

  const $ = s => document.querySelector(s);
  const $$ = s => Array.from(document.querySelectorAll(s));
  let EMERGENCY_CONTACTS = {};

  /*AI Disaster Assistant FAQ*/

  const AI_FAQ = [
    {
      q: "What should I do immediately if my area receives a flood warning?",
      keywords: ["warning","alert","immediately","now","sirens"],
      a: `
<strong>Immediate steps during a flood warning:</strong><br><br>
1. Move yourself and your family to higher ground or a safe upper floor.<br>
2. Keep your phone charged and a power bank ready.<br>
3. Switch off main electrical supply if water is entering the house.<br>
4. Pack your emergency kit (documents, medicines, water, basic food).<br>
5. Follow only official messages from government/relief agencies — avoid rumours.
`
    },
    {
      q: "What should I pack in a flood emergency kit?",
      keywords: ["emergency kit","bag","pack","go bag"],
      a: `
<strong>Essential items for a flood emergency kit:</strong><br><br>
1. Copies of ID, bank passbook, and important documents in a waterproof cover.<br>
2. Drinking water (at least 2–3 litres per person) and dry food/snacks.<br>
3. Basic medicines, first-aid items, and any personal prescription medicines.<br>
4. Torch, extra batteries, power bank, and a basic phone charger.<br>
5. Extra clothes, raincoat, small towel, and essential toiletries.<br>
6. Some cash in small denominations in case ATMs are not available.
`
    },
    {
      q: "How can I prepare my home before the monsoon season?",
      keywords: ["prepare home","monsoon","before rain","preparation"],
      a: `
<strong>Preparing your home before monsoon:</strong><br><br>
1. Check and clear drains, roof outlets, and balcony pipes so water can flow freely.<br>
2. Move important documents and electronics to higher shelves or top floors.<br>
3. Store drinking water in clean containers as a backup.<br>
4. Keep sandbags or bricks ready if your entrance is at low level.<br>
5. Save emergency numbers in your phone and note them on paper as well.<br>
6. Discuss a simple family plan: where to go and whom to call in an emergency.
`
    },
    {
      q: "How do I stay safe if I am already in floodwater?",
      keywords: ["already in water","stuck in water","inside flood","floodwater"],
      a: `
<strong>If you are already in floodwater:</strong><br><br>
1. Avoid moving through fast-flowing water; even shallow water can be dangerous.<br>
2. Do not step into water where you cannot see the ground — there may be open drains or holes.<br>
3. Stay away from electric poles, wires, and transformers — there is shock risk.<br>
4. If water is rising inside a building, move to higher floors and call for help.<br>
5. If you are in a vehicle, do not try to drive through deep water; park safely and move to higher ground if possible.
`
    },
    {
      q: "What should I do if power goes out during heavy rain?",
      keywords: ["power cut","electricity","power outage","light gone"],
      a: `
<strong>During a power cut in heavy rain:</strong><br><br>
1. Use torches or battery lights instead of open flames wherever possible.<br>
2. Unplug non-essential electrical devices to protect them from voltage spikes.<br>
3. Keep your phone on battery-saving mode so you can make calls if needed.<br>
4. Do not touch wet switches or exposed wiring.<br>
5. Listen to battery-powered radio/phone alerts for official updates if available.
`
    },
    {
      q: "How can I protect important documents during floods?",
      keywords: ["documents","aadhar","paper","files"],
      a: `
<strong>Protecting important documents:</strong><br><br>
1. Keep original documents (ID, property papers, certificates) in a waterproof folder or zip-lock bag.<br>
2. Store them on a higher shelf or an upper floor, away from possible water entry.<br>
3. Take clear photos or scans and store them securely on your phone and in cloud storage if possible.<br>
4. Keep one small set of photocopies in your emergency kit for quick use.
`
    },
    {
      q: "What should I do after the flood water recedes?",
      keywords: ["after flood","water recedes","post flood"],
      a: `
<strong>After the water recedes:</strong><br><br>
1. Return home only when authorities say it is safe to do so.<br>
2. Check walls, ceilings, and wiring for visible damage before switching on power.<br>
3. Do not use food items that came in contact with floodwater.<br>
4. Boil drinking water or use safe packaged water until supply is confirmed safe.<br>
5. Take photographs of damage for insurance or relief claim purposes, if applicable.
`
    },
    {
      q: "How can I help elderly or disabled family members in a flood?",
      keywords: ["elderly","disabled","senior","family help"],
      a: `
<strong>Supporting elderly or disabled family members:</strong><br><br>
1. Plan evacuation early — do not wait for water to rise before moving them.<br>
2. Keep their regular medicines, doctor contact, and ID copies in the emergency kit.<br>
3. Assign one responsible person to stay with them continuously during movement.<br>
4. Use wheelchairs, walking aids, or simple chairs as support while moving to safer areas.<br>
5. Inform local volunteers/relief teams if anyone needs special medical help.
`
    },
    {
      q: "How do I stay informed about official flood alerts?",
      keywords: ["alerts","information","news","official"],
      a: `
<strong>Staying informed about flood alerts:</strong><br><br>
1. Follow only official sources such as state disaster management, IMD, or district administration handles.<br>
2. Keep SMS alerts active on your phone; avoid blocking government alert messages.<br>
3. Radio and local news channels can be useful when mobile data is weak.<br>
4. Do not forward unverified messages on social media — confirm before sharing.
`
    },
    {
      q: "What should I teach children about flood safety?",
      keywords: ["children","kids","teach","family safety"],
      a: `
<strong>Teaching children about flood safety:</strong><br><br>
1. Explain in simple language what floods are and why moving to higher ground is important.<br>
2. Show them where the emergency kit is kept and which adults to listen to in an emergency.<br>
3. Tell them never to play in floodwater or near drains and flowing water.<br>
4. Practice a small family drill: where to go and how to leave the house safely.<br>
5. Reassure them and stay calm — children copy adults' behaviour during emergencies.
`
    }
  ];

  function findBestAnswer(userText) {
    const text = userText.toLowerCase();
    // simple keyword match
    for (const item of AI_FAQ) {
      if (item.keywords.some(k => text.includes(k))) return item;
    }
    // fallback: if nothing matches, return generic
    return {
      q: userText,
      a: `
<strong>I did not find an exact match for your question, but here is general flood safety guidance:</strong><br><br>
1. Move to a safe, higher location if there is any risk of water entering your area.<br>
2. Keep your phone charged and emergency numbers handy (112 and state control room).<br>
3. Avoid walking or driving through moving water.<br>
4. Listen to official instructions from local authorities and follow them promptly.<br><br>
You can also tap one of the suggested questions inside the assistant for more specific guidance.
`
    };
  }

  function addAssistantMessage(sender, html) {
    const chat = document.getElementById("assistant-chat");
    if (!chat) return;
    const row = document.createElement("div");
    row.className = `assistant-message-row ${sender}`;
    const avatar = document.createElement("div");
    avatar.className = `assistant-avatar ${sender}`;
    avatar.textContent = sender === "user" ? "🧍" : "🛟";
    const bubble = document.createElement("div");
    bubble.className = `assistant-bubble ${sender}`;
    bubble.innerHTML = html;
    row.appendChild(avatar);
    row.appendChild(bubble);
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
  }

  function openAssistant() {
    const overlay = document.getElementById("ai-assistant");
    if (!overlay) return;
    overlay.classList.remove("hidden");
    const input = document.getElementById("assistant-input");
    if (input) input.focus();

    const chat = document.getElementById("assistant-chat");
    if (chat && chat.childElementCount === 0) {
      addAssistantMessage("bot",
        "Hello, I am your <strong>AI Disaster Assistant</strong>. " +
        "You can ask about flood preparedness, emergency kits, and safety steps. " +
        "Select a question below or type your own."
      );
    }
  }

  function closeAssistant() {
    const overlay = document.getElementById("ai-assistant");
    if (!overlay) return;
    overlay.classList.add("hidden");
  }

  function handleAssistantQuestion(rawText) {
    const text = rawText.trim();
    if (!text) return;
    addAssistantMessage("user", text);
    const { a } = findBestAnswer(text);

    // simple "typing" delay
    setTimeout(() => {
      addAssistantMessage("bot", a);
    }, 400);
  }

  function wireAssistant() {
    const openBtn = document.getElementById("ai-assistant-open");
    const closeBtn = document.getElementById("ai-assistant-close");
    const sendBtn = document.getElementById("assistant-send");
    const input = document.getElementById("assistant-input");

    if (openBtn) openBtn.addEventListener("click", openAssistant);
    if (closeBtn) closeBtn.addEventListener("click", closeAssistant);

    if (sendBtn) {
      sendBtn.addEventListener("click", () => {
        if (!input) return;
        const value = input.value;
        input.value = "";
        handleAssistantQuestion(value);
      });
    }

    if (input) {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          const value = input.value;
          input.value = "";
          handleAssistantQuestion(value);
        }
      });
    }

    // FAQ suggestion buttons
    document.querySelectorAll(".assistant-suggestion").forEach(btn => {
      btn.addEventListener("click", () => {
        const q = btn.getAttribute("data-q") || btn.textContent;
        handleAssistantQuestion(q);
      });
    });
  }

  function createContactCard(name, number) {
    const card = document.createElement("div");
    card.className = "contact-card";

    card.innerHTML = `
      <div class="contact-info">
        <div class="contact-name">${name}</div>
        <div class="contact-number" data-number="${number}">${number}</div>
      </div>
      <button class="copy-btn">Copy</button>
    `;

    // Click number or copy btn copies number
    const copyText = () => {
      navigator.clipboard.writeText(number);
      showToast("Number copied 📋");
    };

    card.querySelector(".contact-number").onclick = copyText;
    card.querySelector(".copy-btn").onclick = copyText;

    return card;
  }


  /*Toast Notification*/
  function showToast(msg, ms = 3000) {
    const t = $("#toast");
    if (!t) return;
    t.textContent = msg;
    t.classList.remove("hidden");
    t.setAttribute("aria-hidden", "false");
    clearTimeout(t._t);
    t._t = setTimeout(() => {
      t.setAttribute("aria-hidden", "true");
      setTimeout(() => t.classList.add("hidden"), 500);
    }, ms);
  }

  /* View Switching */
  function switchView(view) {
    $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
    $$(".nav-btn").forEach(b => b.classList.toggle("nav-btn--active", b.id === `nav-${view}`));
  }

  /* Auth UI State */
  function isLoggedIn() { return !!localStorage.getItem("sessionToken"); }

  function setSignedInUI() {
    const logged = isLoggedIn();
    $("#auth-controls").classList.toggle("hidden", logged);
    $("#user-controls").classList.toggle("hidden", !logged);
    $("#small-user").textContent = logged ? localStorage.getItem("username") || "User" : "No";
  }

  /* Auth Modal Handling */
  function showAuthModal(mode = "login") {
    $("#authModal").classList.remove("hidden");
    switchAuthTab(mode);
  }
  function hideAuthModal() { $("#authModal").classList.add("hidden"); }

  function switchAuthTab(mode) {
    $$(".tab").forEach(t => t.classList.remove("active"));
    document.querySelector(`.tab[data-mode="${mode}"]`).classList.add("active");
    $("#loginFields").classList.toggle("hidden", mode !== "login");
    $("#signupFields").classList.toggle("hidden", mode !== "signup");
    $("#authSubmit").textContent = mode === "login" ? "Login" : "Sign up";
    $("#authMsg").textContent = "";
  }

  async function onAuthSubmit() {
    const mode = document.querySelector(".tab.active").dataset.mode;
    const msg = $("#authMsg");
    msg.textContent = "Processing...";

    try {
      if (mode === "login") {
        const username = $("#loginUser").value.trim();
        const password = $("#loginPass").value;
        if (!username || !password) return msg.textContent = "Enter all fields";
        const r = await fetch(AUTH_LOGIN, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password })
        });
        if (!r.ok) throw new Error(await r.text());
        const j = await r.json();
        localStorage.setItem("sessionToken", j.token);
        localStorage.setItem("username", username);
        hideAuthModal();
        setSignedInUI();
        showToast("Login successful ✅");
      } else {
        const full = $("#signupFull").value.trim();
        const user = $("#signupUser").value.trim();
        const pass = $("#signupPass").value;
        if (!full || !user || !pass) return msg.textContent = "Fill all fields";
        const r = await fetch(AUTH_SIGNUP, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: user, password: pass, full_name: full })
        });
        if (!r.ok) throw new Error(await r.text());
        const j = await r.json();
        localStorage.setItem("sessionToken", j.token || "demo-token");
        localStorage.setItem("username", j.username || user);
        hideAuthModal();
        setSignedInUI();
        showToast("Account created 🎉");
      }
    } catch (e) {
      msg.textContent = "Auth endpoint unreachable";
      showToast("Server unreachable");
    }
  }

  function wireAuth() {
    $("#btn-login").onclick = () => showAuthModal("login");
    $("#btn-signup").onclick = () => showAuthModal("signup");
    $("#authClose").onclick = hideAuthModal;
    $("#authCancel").onclick = hideAuthModal;
    $$(".tab").forEach(t => t.addEventListener("click", () => switchAuthTab(t.dataset.mode)));
    $("#authSubmit").onclick = onAuthSubmit;
  }

  /* -----------------------
     State & District Dropdown
  ----------------------- */
  let STATES_DISTRICTS = {};

  async function loadStatesAndDistricts() {
    const fallback = {
      "Uttar Pradesh": ["Lucknow", "Kanpur", "Varanasi"],
      "Bihar": ["Patna", "Gaya", "Muzaffarpur"]
    };

    try {
      const res = await fetch("states_districts.json", { cache: "no-store" });
      if (!res.ok) throw new Error("Missing states_districts.json");
      STATES_DISTRICTS = await res.json();
    } catch (err) {
      console.warn("Using fallback states data", err);
      STATES_DISTRICTS = fallback;
    }

    populateStateDropdown();
  }

  function populateStateDropdown() {
    const select = $("#stateSelect");
    if (!select) return;
    select.innerHTML = `<option value="">-- Select a State --</option>`;
    Object.keys(STATES_DISTRICTS).sort().forEach(state => {
      const opt = document.createElement("option");
      opt.value = state;
      opt.textContent = state;
      select.appendChild(opt);
    });
    select.onchange = (event) => {
      onStateChange(event);
      updateLivePreview();
    };

  }

  function onStateChange(e) {
    const state = e.target.value;
    const districtSelect = $("#districtSelect");
    districtSelect.innerHTML = `<option value="">Loading districts...</option>`;

    if (!state || !STATES_DISTRICTS[state]) {
      districtSelect.innerHTML = `<option value="">-- Select District --</option>`;
      return;
    }

    const districts = STATES_DISTRICTS[state];
    districtSelect.innerHTML = `<option value="">-- Select District --</option>`;
    districts.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = d;
      districtSelect.appendChild(opt);
    });
    
    districtSelect.onchange = updateLivePreview;

    showToast(`Loaded ${districts.length} districts`);
    updateLivePreview();
  }

  function updateLivePreview() {
    const state = $("#stateSelect").value || "Not selected";
    const district = $("#districtSelect").value || "Not selected";

    $("#previewJson").textContent = JSON.stringify({
      state,
      district
    }, null, 2);
  }

  function updateLivePreview() {
    const state = $("#stateSelect").value || "Not selected";
    const district = $("#districtSelect").value || "Not selected";

    $("#previewJson").textContent = JSON.stringify({
      state,
      district
    }, null, 2);
  }

  function onStateSearch(e) {
    const query = e.target.value.trim().toLowerCase();
    const stateSelect = $("#stateSelect");
    if (!stateSelect) return;

    // Clear existing dropdown
    stateSelect.innerHTML = `<option value="">-- Select a State --</option>`;

    // If nothing typed, show all
    const states = Object.keys(STATES_DISTRICTS);
    const filtered = query
      ? states.filter(s => s.toLowerCase().includes(query))
      : states;

    filtered.sort().forEach(state => {
      const opt = document.createElement("option");
      opt.value = state;
      opt.textContent = state;
      stateSelect.appendChild(opt);
    });

    if (filtered.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No match found";
      stateSelect.appendChild(opt);
    }
  }

  /* -----------------------
     Prediction Logic (Final)
  ----------------------- */
  function resetPredictForm() {
    $("#stateSelect").value = "";
    $("#districtSelect").innerHTML = `<option value="">-- Select District --</option>`;
    $("#previewJson").textContent = "No selection yet.";
    $("#predictStatus").textContent = "Form reset.";
    showToast("Form reset ✅");
  }

  async function runPrediction() {
    const state = $("#stateSelect").value;
    const district = $("#districtSelect").value;
    const statusEl = $("#predictStatus");

    if (!state || !district) {
      showToast("Please select both state and district");
      return;
    }

    if (!isLoggedIn()) {
      showToast("Please login to make predictions");
      return;
    }

    statusEl.textContent = "Running prediction...";
    const predictBtn = $("#predictBtn");
    predictBtn.disabled = true;

    try {
      const resp = await fetch(`${BACKEND}/predict/${encodeURIComponent(state)}/${encodeURIComponent(district)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timestamp: Math.floor(Date.now() / 1000) })
      });

      if (!resp.ok) {
        const txt = await resp.text();
        showToast(`Prediction failed: ${txt}`);
        statusEl.textContent = "Prediction failed ❌";
        predictBtn.disabled = false;
        return;
      }

      const data = await resp.json();
      displayResults(data, state, district);
      switchView("results"); // ✅ Show results page
      showToast("Prediction complete ✅");
      statusEl.textContent = "Completed!";
    } catch (err) {
      console.error("Prediction error:", err);
      showToast("Backend unreachable ❌");
      statusEl.textContent = "Network error";
    } finally {
      predictBtn.disabled = false;
    }
  }

  function displayResults(data, state, district) {
    const risk = data.risk || data.risk_level || "Unknown";
    const score = data.score || data.predicted_flood_risk || "N/A";
    const f = data.features || data.features_used || {};

    // --- Risk Badge Update ---
    const badge = $("#riskBadge");
    badge.textContent = risk.toUpperCase();
    badge.className = "risk-badge"; 

    if (/low/i.test(risk)) badge.classList.add("low");
    else if (/moderate/i.test(risk)) badge.classList.add("moderate");
    else badge.classList.add("high");

    // --- Metric Tiles Update ---
    $("#resultDistrict").textContent = district;
    $("#resultScore").textContent = score;
    $("#resultTemp").textContent = f.temp ?? "N/A";
    $("#resultHumidity").textContent = f.humidity ?? "N/A";
    $("#resultRain").textContent = f.rainfall ?? "N/A";
    $("#resultWind").textContent = f.wind_speed ?? "N/A";
    // Update Last Prediction Summary on Home
    $("#last-pred").textContent = `${district}, ${state}`;
    $("#app-status").textContent = `Flood Risk: ${risk}`;
    localStorage.setItem("lastPrediction", JSON.stringify({ state, district, risk }));


    $("#resultTime").textContent = new Date().toLocaleString();
    showResultEmergencyContacts(state);
    renderStateEmergencyContacts(state);
  }

  function renderStateEmergencyContacts(state) {
    const list = $("#resultEmergencyList");
    if (!list) return;
    list.innerHTML = ""; // Reset

    const national = EMERGENCY_CONTACTS?.National || {};
    const stateContacts = EMERGENCY_CONTACTS?.[state] || {};

    function addContact(name, number) {
      const div = document.createElement("div");
      div.className = "contact-card";
      div.innerHTML = `
        <div class="contact-info">
          <div class="contact-name">${name}</div>
          <div class="contact-number" data-num="${number}">${number}</div>
        </div>
        <button class="copy-btn" data-copy="${number}">Copy</button>
      `;
      list.appendChild(div);
    }

    Object.entries(national).forEach(([label, num]) => addContact(label, num));
    Object.entries(stateContacts).forEach(([label, num]) => addContact(label, num));

    // Copy functionality
    list.addEventListener("click", (e) => {
      const btn = e.target.closest(".copy-btn");
      if (!btn) return;
      const num = btn.dataset.copy;
      navigator.clipboard.writeText(num);
      showToast("Number copied 📋");
    });
  }

  async function showResultEmergencyContacts(state) {
    try {
      const res = await fetch("emergency_contacts.json");
      const data = res.ok ? await res.json() : {};

      const national = data["National"] || {};
      const stateContacts = data[state] || {};

      const container = $("#resultEmergency");
      container.innerHTML = "";

      // National first
      Object.entries(national).forEach(([name, number]) => {
        container.appendChild(createContactCard(name, number));
      });

      // Then current prediction state contacts
      Object.entries(stateContacts).forEach(([name, number]) => {
        container.appendChild(createContactCard(name, number));
      });

    } catch (err) {
      console.error(err);
    }
  }

  /* Emergency Section */
  async function renderEmergency() {
    try {
      const r = await fetch("emergency_contacts.json");
      EMERGENCY_CONTACTS = await r.json();
    
      const national = EMERGENCY_CONTACTS.National;
      const container = $("#emergencyList");
      container.innerHTML = "";

      Object.entries(national).forEach(([label, num]) => {
        const card = document.createElement("div");
        card.className = "contact-card";
        card.innerHTML = `
          <div class="contact-info">
            <div class="contact-name">${label}</div>
            <div class="contact-number" data-num="${num}">${num}</div>
          </div>
          <button class="copy-btn" data-copy="${num}">Copy</button>
        `;
        container.appendChild(card);
      });

    } catch (e) {
      console.error("Emergency JSON load failed", e);
    }
  }

  /* Navigation */
  function wireNav() {
    ["home", "predict", "about", "emergency", "profile"].forEach(id => {
      const b = $("#nav-" + id);
      if (b) b.addEventListener("click", () => switchView(id));
    });

    const ctaPredict = $("#cta-predict");
    if (ctaPredict) ctaPredict.onclick = () => switchView("predict");
    const ctaAbout = $("#cta-about");
    if (ctaAbout) ctaAbout.onclick = () => switchView("about");
    const ctaEmergency = $("#cta-emergency");
    if (ctaEmergency) ctaEmergency.onclick = () => switchView("emergency");

    const resetBtn = $("#resetBtn");
    if (resetBtn) resetBtn.onclick = resetPredictForm;
    const predictBtn = $("#predictBtn");
    if (predictBtn) predictBtn.onclick = runPrediction;

    const backBtn = $("#btn-back");
    if (backBtn) backBtn.onclick = () => switchView("predict");
    const emergencyBtn = $("#btn-emergency");
    if (emergencyBtn) emergencyBtn.onclick = () => switchView("emergency");

    // Profile dropdown toggle
    const profileBtn = $("#profile-btn");
    const profileMenu = $("#profile-menu");
    if (profileBtn && profileMenu) {
      profileBtn.addEventListener("click", () => {
        profileMenu.classList.toggle("hidden");
      });

      document.addEventListener("click", (e) => {
        if (!profileBtn.contains(e.target) && !profileMenu.contains(e.target)) {
          profileMenu.classList.add("hidden");
        }
      });

      // Profile page open
      const profileLink = $("#btn-profile");
      if (profileLink) profileLink.onclick = () => {
        profileMenu.classList.add("hidden");
        switchView("profile");
      };

      // Logout functionality
      const logoutBtn = $("#btn-logout");
      if (logoutBtn) logoutBtn.onclick = () => {
        localStorage.removeItem("sessionToken");
        localStorage.removeItem("username");
        showToast("Logged out successfully 👋");
        profileMenu.classList.add("hidden");
        $("#auth-controls").classList.remove("hidden");
        $("#user-controls").classList.add("hidden");
        switchView("home");
      };
    }
  }

  /* -----------------------
     Initialization
  ----------------------- */
  function init() {
    wireNav();
    wireAuth();
    setSignedInUI();
    const lp = localStorage.getItem("lastPrediction");
      if (lp) {
        const { state, district, risk } = JSON.parse(lp);
        $("#last-pred").textContent = `${district}, ${state}`;
        $("#app-status").textContent = `Flood Risk: ${risk}`;
      }

    renderEmergency();
    loadStatesAndDistricts();
    const stateSearch = $("#state-input");
    if (stateSearch) stateSearch.addEventListener("input", onStateSearch);
    wireAssistant();
    
    showToast("App ready ✅");
  }

  // Bottom navigation handlers
  const bottomMap = {
    "bottom-home": "view-home",
    "bottom-predict": "view-predict",
    "bottom-emergency": "view-emergency",
    "bottom-about": "view-about"
  };

  Object.keys(bottomMap).forEach(btnId => {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    btn.addEventListener("click", () => {
      // remove active from all
      document.querySelectorAll(".bottom-item").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      // hide all views
      document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));

      // show selected view
      document.getElementById(bottomMap[btnId]).classList.add("active");
    });
  });
  document.addEventListener("DOMContentLoaded", init);
})();