(() => {
  "use strict";

  /*Configuration*/
  const BACKEND = "https://early-flood-predictor.onrender.com";
  const AUTH_LOGIN = `${BACKEND}/auth/login`;
  const AUTH_SIGNUP = `${BACKEND}/auth/signup`;

  const $ = s => document.querySelector(s);
  const $$ = s => Array.from(document.querySelectorAll(s));
  let EMERGENCY_CONTACTS = {};

  let userMarker = null;
  let riskMarkers = {};

  /*Geolocation*/
  let cordovaReady = false;

  document.addEventListener("deviceready", function () {
  	console.log("Cordova ready");
	  showToast("Cordova ready");

  	if (typeof FirebasePlugin === "undefined") {
	  	console.error("FirebasePlugin not available");
		  showToast("Firebase not available");
	  	return;
	  }

  	// STEP 1: Permission FIRST
	  FirebasePlugin.grantPermission();

  	// STEP 2: Get Token → THEN subscribe
	  FirebasePlugin.getToken(function(token) {
		  console.log("Token:", token);
		  showToast("Token received");

  		// STEP 3: Subscribe AFTER token
	  	FirebasePlugin.subscribe("all", function() {
		  	console.log("Subscribed to topic 'all'");
			  showToast("Subscribed");
		  }, function(err) {
			  console.error("Subscribe error:", err);
		  });

  	}, function(err) {
	  	console.error("Token error:", err);
	  });

  	// STEP 4: Listener
	  FirebasePlugin.onMessageReceived(function(message) {
		  console.log("Notification received:", message);

  		FirebasePlugin.onMessageReceived(function(message) {
	      console.log("Notification received:", message);

      	const body = message.body || message.data?.body;

      	if (!message.tap) {
		      alert(body);
	      }
      });

  	}, function(error) {
	  	console.error("Notification error:", error);
	  });

  }, false);

  function addAssistantMessage(sender, html) {
    const chat = document.getElementById("assistant-chat");
    if (!chat) return;
    const row = document.createElement("div");
    row.className = `assistant-message-row ${sender}`;
    const avatar = document.createElement("div");
    avatar.className = `assistant-avatar ${sender}`;
    if (sender === "user") {
        avatar.textContent = "🧍";
    } else {
        const img = document.createElement("img");
        img.src = "assets/bot-icon.png";   
        img.alt = "AI";
        avatar.appendChild(img);
    }
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
    document.body.classList.add("chat-open");
    const input = document.getElementById("assistant-input");
    if (input) input.focus();

    const chat = document.getElementById("assistant-chat");
    if (chat && chat.childElementCount === 0) {
      addAssistantMessage("bot",
        "Hello, I am your <strong>MEGHDOOT </strong>your AI Disaster Assistant. " +
        "You can ask about flood preparedness, emergency kits, and safety steps etc. " +
        "So, how can I help you?"
      );
    }
  }

  function closeAssistant() {
    const overlay = document.getElementById("ai-assistant");
    if (!overlay) return;
    overlay.classList.add("hidden");
    document.body.classList.remove("chat-open");
  }

  async function handleAssistantQuestion(rawText) {

    const text = rawText.trim();
    if (!text) return;

    addAssistantMessage("user", text);

    // show temporary typing message
    const chat = document.getElementById("assistant-chat");
    const typingRow = document.createElement("div");
    typingRow.className = "assistant-message-row bot";
    typingRow.innerHTML = `
      <div class="assistant-avatar bot">
            <img src="assets/bot-icon.png">
        </div>
      <div class="assistant-bubble bot">AI is typing...</div>
    `;
    chat.appendChild(typingRow);
    chat.scrollTop = chat.scrollHeight;

    try {

      const res = await fetch(`${BACKEND}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: text,
          history: []
        })
      });

      const data = await res.json();
      

      typingRow.remove();

      addAssistantMessage("bot", data.reply);
      document.getElementById("assistant-input").blur();
      
    } catch (err) {

      typingRow.remove();

      addAssistantMessage(
        "bot",
        "Unable to contact the AI assistant. Please try again."
      );

      console.error(err);
    }
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
      showToast("Number copied");
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

    if (view === "predict") {
      const statusEl = document.getElementById("predictStatus");
      if (statusEl) {
        statusEl.textContent = "Ready.";
      }
    }
  }

  /* Auth UI State */
  function isLoggedIn() { return !!localStorage.getItem("sessionToken"); }

  function setSignedInUI() {
    const logged = isLoggedIn();
    $("#auth-controls").classList.toggle("hidden", logged);
    $("#user-controls").classList.toggle("hidden", !logged);
    $("#small-user").textContent = logged ? localStorage.getItem("username") || "User" : "No";
  }

  /* Auth Model Handling */
  function showAuthModel(mode = "login") {
    $("#authModel").classList.remove("hidden");
    switchAuthTab(mode);
  }
  function hideAuthModel() { $("#authModel").classList.add("hidden"); }

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
        if (!r.ok) {
          const errText = await r.text();
          console.error("Login error:", errText);
          throw new Error(errText);
        }
        const j = await r.json();
        localStorage.setItem("sessionToken", j.token);
        localStorage.setItem("username", username);
        hideAuthModel();
        setSignedInUI();
        showToast("Login successful");
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
        hideAuthModel();
        setSignedInUI();
        showToast("Account created");
      }
    } catch (e) {
      console.error("Auth error:", e);
      msg.textContent = e.message || "Login failed";
      showToast(e.message || "Server error");
    }
  }

  function wireAuth() {
    $("#btn-login").onclick = () => showAuthModel("login");
    $("#btn-signup").onclick = () => showAuthModel("signup");
    $("#authClose").onclick = hideAuthModel;
    $("#authCancel").onclick = hideAuthModel;
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

  // Prediction Logic
  function resetPredictForm() {
    $("#stateSelect").value = "";
    $("#districtSelect").innerHTML = `<option value="">-- Select District --</option>`;
    $("#previewJson").textContent = "No selection yet.";
    $("#predictStatus").textContent = "Form reset.";
    showToast("Form reset");
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
    if (predictBtn.disabled) return;
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
        statusEl.textContent = "Prediction failed";
        predictBtn.disabled = false;
        return;
      }

      const data = await resp.json();
      if (!data || !data.current_prediction) {
        showToast("Invalid prediction response");
        return;
      }
      displayResults(data, state, district);
      switchView("results"); // 
      showToast("Prediction complete");
      statusEl.textContent = "Completed!";
    } catch (err) {
      console.error("Prediction error:", err);
      showToast("Backend unreachable");
      statusEl.textContent = "Network error";
    } finally {
      predictBtn.disabled = false;
    }
  }

  function displayResults(data, state, district) {

    const risk = data.current_prediction.risk_level || "Unknown";
    // Get coordinates from backend response OR fetch again
    console.log("Prediction result:", state, district, risk);
    fetch(`${BACKEND}/coordinates/${encodeURIComponent(state)}/${encodeURIComponent(district)}`)
      .then(res => {
        if (!res.ok) throw new Error("API failed");
        return res.json();
      })
      .then(coords => {
        console.log("Coordinates received:", coords);
        if (map) {
	        updateMapMarker(state, district, risk, coords.lat, coords.lon);
        } else {
	        console.log("Map not ready yet");
        }
      })
      .catch(err => console.error("Map update failed:", err));
    const score = data.current_prediction.score ?? "N/A";
    const f = data.features || {};

    // Risk badge
    const badge = $("#riskBadge");
    badge.textContent = risk.toUpperCase();
    badge.className = "risk-badge";

    if (/low/i.test(risk)) badge.classList.add("low");
    else if (/moderate/i.test(risk)) badge.classList.add("moderate");
    else badge.classList.add("high");

    // Update values
    $("#resultDistrict").textContent = district;
    $("#resultScore").textContent = score;

    $("#resultTemp").textContent = f.temp ?? "N/A";
    $("#resultHumidity").textContent = f.humidity ?? "N/A";
    $("#resultRain").textContent = f.current_rain ?? "N/A";
    $("#resultRain24h").textContent = f.rain_24h ?? "N/A";
    $("#resultRain7d").textContent = f.rain_7d ?? "N/A";
    $("#resultWind").textContent = f.wind_speed ?? "N/A";

    // Save prediction summary
    $("#last-pred").textContent = `${district}, ${state}`;
    $("#app-status").textContent = `Flood Risk: ${risk}`;

    localStorage.setItem(
      "lastPrediction",
      JSON.stringify({ state, district, risk })
    );

    $("#resultTime").textContent = new Date().toLocaleString();

    showResultEmergencyContacts(state);
    renderStateEmergencyContacts(state);
    const today = new Date().toISOString().split("T")[0];

    const combinedData = [
      {
        date: today,
        risk: data.current_prediction.score,
        label: "Today"
      },
      ...data.future_predictions.map((d, i) => ({
        date: d.date,
        risk: d.risk,
        label: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short' })
      }))
    ];
    const uniqueData = [];
    const seenDates = new Set();

    combinedData.forEach(d => {
      if (!seenDates.has(d.date)) {
        seenDates.add(d.date);
        uniqueData.push(d);
      }
    });

    renderForecast(uniqueData);
  }

  function renderForecast(futureData) {
    const container = document.getElementById("forecastDays");
    const summary = document.getElementById("forecastSummary");

    container.innerHTML = "";

    if (!futureData || futureData.length === 0) return;

    let maxDay = futureData[0];

    futureData.forEach((day, index) => {
      const div = document.createElement("div");
      div.className = "forecast-day";
      div.innerHTML = `
        <strong>${new Date(day.date).toDateString().slice(0, 3)}</strong><br>
        ${(day.risk * 100).toFixed(0)}%
      `;

      if (index === 0) div.classList.add("active");
      if (day.risk > maxDay.risk) maxDay = day;

      div.onclick = () => {
        document.querySelectorAll(".forecast-day").forEach(d => d.classList.remove("active"));
        div.classList.add("active");
        updateSelectedDay(day);
      };

      container.appendChild(div);
    });

    summary.textContent = `Highest flood risk expected on ${new Date(maxDay.date).toDateString()}`;

    drawRiskChart(futureData);

    updateSelectedDay(futureData[0]);
  }

  function updateSelectedDay(day) {
    const badge = document.getElementById("riskBadge");

    const risk = day.risk;

    let label = "High";
    if (risk > 0.90) label = "Low";
    else if (risk > 0.70) label = "Moderate";

    badge.textContent = label.toUpperCase();
    badge.className = "risk-badge";

    if (label === "Low") badge.classList.add("low");
    else if (label === "Moderate") badge.classList.add("moderate");
    else badge.classList.add("high");
  }

  function drawRiskChart(data) {
    const ctx = document.getElementById("riskChart").getContext("2d");

    if (window.riskChartInstance) {
      window.riskChartInstance.destroy();
    }

    window.riskChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: data.map(d => d.label || new Date(d.date).toDateString().slice(0, 3)),
        datasets: [{
          label: "Flood Risk",
          data: data.map(d => Number(d.risk)),
          tension: 0.4,
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,

        scales: {
          y: {
            min: 0,
            max: 1,
            ticks: {
              stepSize: 0.1 
            }
          }
        }
      }
    });
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
      showToast("Number copied");
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
        showToast("Logged out successfully");
        profileMenu.classList.add("hidden");
        $("#auth-controls").classList.remove("hidden");
        $("#user-controls").classList.add("hidden");
        switchView("home");
      };
    }
  }

  
  // Initialization
  
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
    
    showToast("App ready");
  }

  function getMarkerColor(risk) {
    if (/high/i.test(risk)) return "red";
    if (/moderate/i.test(risk)) return "orange";
    return null;
  }

	function updateMapMarker(state, district, risk, lat, lon) {
		const key = `${state}|${district}`;

		// REMOVE MARKER IF LOW
		if (/low/i.test(risk)) {
			if (riskMarkers[key]) {
				riskMarkers[key].remove();
				delete riskMarkers[key];
			}
		} else {
			const color = getMarkerColor(risk);
			if (!color) return;

			const time = new Date().toLocaleString();

			const el = document.createElement("div");
			el.style.width = "14px";
			el.style.height = "14px";
			el.style.borderRadius = "50%";
			el.style.background = color;
			el.style.border = "2px solid white";
			el.style.zIndex = "9999";

			const popup = new maplibregl.Popup({ offset: 25 }).setHTML(
				`<strong>${district}</strong><br>${risk.toUpperCase()}<br>${time}`
			);

			// Remove old marker if exists
			if (riskMarkers[key]) {
				riskMarkers[key].remove();
			}

			const marker = new maplibregl.Marker({ element: el })
				.setLngLat([lon, lat])
				.setPopup(popup)
				.addTo(map);

			riskMarkers[key] = marker;
		}
	}

  // Bottom navigation handlers
  const bottomMap = {
    "bottom-home": "view-home",
    "bottom-predict": "view-predict",
    "bottom-map": "view-map",
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
      const viewId = bottomMap[btnId];
      document.getElementById(viewId).classList.add("active");

      // Initialize map when Map page opens
      if (viewId === "view-map" && !map) {
        setTimeout(() => {
          initMap();
          showUserLocation();
        }, 200);
      }
    });
  });
  document.addEventListener("DOMContentLoaded", init);

  let deviceReady = false;

  async function loadAllMarkers() {
  	try {
	  	Object.values(riskMarkers).forEach(m => m.remove());
		  riskMarkers = {};

  		const res = await fetch(`${BACKEND}/risk-markers`);
	  	const data = await res.json();

  		data.forEach(item => {
	  		updateMapMarker(
		  		item.state,
			  	item.district,
				  item.risk,
  				item.lat,
	  			item.lon
		  	);
		  });

  		console.log("Markers loaded:", data.length);

  	} catch (err) {
	  	console.error("Failed to load markers:", err);
	  }
  }
  
  /* ---------------- LIVE LOCATION FEATURE ---------------- */

  document.addEventListener("deviceready", onDeviceReady, false);

  function onDeviceReady() {

    cordova.plugins.diagnostic.requestLocationAuthorization(function(status){
        console.log("Location permission: " + status);
    }, function(error){
        console.error(error);
    });
  }

  const locationStatus = document.getElementById("locationStatus");

  document.addEventListener("DOMContentLoaded", () => {

    const liveBtn = document.getElementById("btnLiveLocation");
    if (!liveBtn) return;

    liveBtn.addEventListener("click", getLiveLocation);
  });

  function getLiveLocation() {
      if (!deviceReady && !cordovaReady) {
          locationStatus.innerText = "Please wait, app is still loading...";
          return;
      }

    if (!navigator.geolocation) {
        locationStatus.innerText = "Geolocation not supported on this device.";
        return;
    }

    cordova.plugins.diagnostic.isLocationEnabled(function(enabled){

        if(!enabled){
            locationStatus.innerHTML = `
              Location is turned off.<br>
              Please enable location to fetch flood risk for your area.<br><br>
              <button id="openLocationSettings">Turn On Location</button>
            `;

            document.getElementById("openLocationSettings").onclick = function(){
                cordova.plugins.diagnostic.switchToLocationSettings();
            };
            return;
        }

        // If location is ON → fetch location
        locationStatus.innerText = "Fetching your location...";

        navigator.geolocation.getCurrentPosition(
            successLocation,
            errorLocation,
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 0
            }
        );

    }, function(error){
        console.error("Location check failed:", error);
        locationStatus.innerText = "Unable to check location settings.";
    });
  }

  async function successLocation(position) {

    const lat = position.coords.latitude;
    const lon = position.coords.longitude;

    locationStatus.innerText =
      `Detected Location: ${lat.toFixed(4)}, ${lon.toFixed(4)}`;

    // 🔥 Find nearest district using coordinates dataset
    if (!DISTRICT_COORDS || Object.keys(DISTRICT_COORDS).length === 0) {
      locationStatus.innerText = "Loading district database... try again";
      return;
    }

    const result = findNearestDistrict(lat, lon);

    console.log("Detected District:", result);

    // Auto-fill dropdown
    autoSelectStateDistrict(result.state, result.district);

    // Send to backend for prediction
    fetch(`${BACKEND}/predict-by-coordinates`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        latitude: lat,
        longitude: lon
      })
    })
    .then(res => res.json())
    .then(data => {
        console.log("Prediction:", data);
    })
    .catch(() => {
        locationStatus.innerText = "Prediction failed";
    });
  }

  function errorLocation(err) {

    console.log("Location error:", err);

    switch(err.code) {
        case 1:
            locationStatus.innerText = "Permission denied for location.";
            break;
        case 2:
            locationStatus.innerText = "Location unavailable. Turn on GPS.";
            break;
        case 3:
            locationStatus.innerText = "Location request timed out. Please check if your ocation is turned on and try again.";
            break;
        default:
            locationStatus.innerText = "Unable to fetch location.";
    }
  }

  /* ---------------- MAP + FLOOD MARKING (MapLibre) ---------------- */

  let map;

  function initMap(lat = 21.25, lon = 81.63) {

    map = new maplibregl.Map({
      container: 'map',
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: [lon, lat],
      zoom: 6,
      maxBounds: [
        [67.5, 6.5],
        [97.5, 37.5]
      ]
    });

    map.on("load", () => {
      const saved = JSON.parse(localStorage.getItem("riskMarkersData") || "[]");

      saved.forEach(item => {
        fetch(`${BACKEND}/coordinates/${encodeURIComponent(item.state)}/${encodeURIComponent(item.district)}`)
          .then(res => res.json())
          .then(coords => {
            updateMapMarker(item.state, item.district, item.risk, coords.lat, coords.lon);
          })
          .catch(err => console.error("Error loading marker:", err));
      });
    });

    map.addControl(new maplibregl.NavigationControl());
  }

  function showUserLocation() {
    const statusText = document.getElementById("mapLocationStatus");

    if (!navigator.geolocation) {
      statusText.innerText = "Geolocation not supported on this device.";
      return;
    }

    navigator.geolocation.getCurrentPosition(
      function(position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        statusText.style.display = "none";

      if (map) {
          map.flyTo({
            center: [lon, lat],
            zoom: 13
          });

          if (userMarker) {
            userMarker.remove();
          }

          const el = document.createElement("div");
          el.className = "blue-dot";

          el.addEventListener("click", function() {

            map.flyTo({
              center: [lon, lat],
              zoom: 15,
              essential: true
            });

          });

          userMarker = new maplibregl.Marker({
            element: el,
            anchor: "center"
          })
          .setLngLat([lon, lat])
          .addTo(map);
        }
      },

      function() {
        statusText.innerText =
          "Turn on your device location to see yourself on the map.";
      },
      {
        enableHighAccuracy: true
      }
    );
}

  function autoSelectStateDistrict(stateName, districtName) {

    const stateSelect = document.getElementById("stateSelect");
    const districtSelect = document.getElementById("districtSelect");

    if (!stateSelect || !districtSelect) return;

    // Normalize text (important)
    const clean = str =>
      str?.toLowerCase().replace(" district","").trim();

    const targetState = clean(stateName);
    const targetDistrict = clean(districtName);

    // Select State
    for (let i = 0; i < stateSelect.options.length; i++) {
      const option = stateSelect.options[i];
      if (clean(option.text) === targetState) {
        stateSelect.selectedIndex = i;

        // Trigger change event so districts load
        stateSelect.dispatchEvent(new Event("change"));
        break;
      }
    }

    // Wait for district dropdown to populate
    setTimeout(() => {

      for (let i = 0; i < districtSelect.options.length; i++) {
        const option = districtSelect.options[i];
        if (clean(option.text) === targetDistrict) {
          districtSelect.selectedIndex = i;
          break;
        }
      }

    }, 500); // small delay so districts load first
  }

  function findNearestDistrict(userLat, userLon) {

    let closestDistrict = null;
    let closestState = null;
    let minDistance = 999999;

    for (const state in DISTRICT_COORDS) {

      for (const district in DISTRICT_COORDS[state]) {

        const d = DISTRICT_COORDS[state][district];

        const dist = getDistance(userLat, userLon, d.lat, d.lon);

        if (dist < minDistance) {
          minDistance = dist;
          closestDistrict = district;
          closestState = state;
        }
      }
    }

    return {state: closestState, district: closestDistrict};
  }

  function getDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth radius km
    const dLat = (lat2 - lat1) * Math.PI/180;
    const dLon = (lon2 - lon1) * Math.PI/180;

    const a =
      Math.sin(dLat/2) * Math.sin(dLat/2) +
      Math.cos(lat1*Math.PI/180) *
      Math.cos(lat2*Math.PI/180) *
      Math.sin(dLon/2) * Math.sin(dLon/2);

    return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
  }
  
  	let startY = 0;
	let pulling = false;
	let refreshTriggered = false;

	const refreshEl = document.getElementById("pullRefresh");

	document.addEventListener("touchstart", (e) => {

		// Only allow refresh if touch starts near top of screen
		if (e.touches[0].clientY > 80) {
			startY = null;
			return;
		}

		startY = e.touches[0].clientY;
		pulling = false;
		refreshTriggered = false;

	});

	document.addEventListener("touchmove", (e) => {

		if (startY === null) return;

		const currentY = e.touches[0].clientY;
		const pullDistance = currentY - startY;

		// Do not trigger refresh inside map
		if (e.target.closest("#map")) return;

		// Only trigger refresh when pulling down strongly
		if (pullDistance > 90 && !refreshTriggered) {

			pulling = true;
			refreshTriggered = true;

			refreshEl.classList.add("active");

		}

	});

	document.addEventListener("touchend", () => {

		if (pulling) {

			refreshEl.classList.add("spin");

			setTimeout(() => {

				refreshEl.classList.remove("spin");
				refreshEl.classList.remove("active");

				refreshApp();

			}, 900);

		}

		pulling = false;
		startY = null;

	});

  function refreshApp(){
    const currentView = document.querySelector(".view.active");
    const currentId = currentView ? currentView.id : null;

    location.reload();

    if(currentId){
      setTimeout(()=>{
        showView(currentId);
      },100);
    }
  }
})();
