(function () {
  "use strict";

  /* =========================================================================
     RULE ENGINE — a JS port of the same rubric used by the backend
     (app/rubric.py). Kept here so this page is a real, working demo rather
     than a scripted mockup: classification, rule matching, retrieval, PII
     redaction, checklist generation and comparison all run for real,
     in-browser, against whatever text the user pastes in.
     ========================================================================= */

  var RULES = [
    { id: "security_deposit_terms", title: "Security deposit amount & return terms", category: "financial",
      keywords: ["security deposit", "damage deposit"], severity: "high", appliesTo: ["residential_lease"],
      detailed: "Confirm the deposit amount, the timeline for its return after move-out, and what deductions are allowed.",
      simple: "Ask: how much is the deposit, and when do I get it back?" },
    { id: "rent_due_date_and_late_fees", title: "Rent due date & late fee terms", category: "financial",
      keywords: ["late fee", "due date", "grace period"], severity: "medium", appliesTo: ["residential_lease"],
      detailed: "Look for the exact due date, any grace period, and how late fees are calculated — flat fee vs. daily accrual.",
      simple: "Ask: when is rent due, and what happens if it's late?" },
    { id: "maintenance_responsibility", title: "Maintenance & repair responsibilities", category: "maintenance",
      keywords: ["maintenance", "repair", "habitable", "habitability"], severity: "medium", appliesTo: ["residential_lease"],
      detailed: "Leases should state who fixes what. Silence here often defaults to landlord-favorable interpretations.",
      simple: "Ask: who fixes things when they break?" },
    { id: "entry_notice", title: "Landlord entry & notice requirements", category: "access",
      keywords: ["right of entry", "notice to enter", "access to the premises"], severity: "medium", appliesTo: ["residential_lease"],
      detailed: "Most states require advance notice before a landlord enters except in emergencies — check the notice window stated here.",
      simple: "Ask: how much warning do I get before the landlord comes in?" },
    { id: "early_termination", title: "Early termination / lease-break terms", category: "termination",
      keywords: ["early termination", "break the lease", "lease break", "termination fee"], severity: "low", appliesTo: ["residential_lease"],
      detailed: "If your plans might change, know the exact penalty for ending the lease early.",
      simple: "Ask: what does it cost me to leave early?" },
    { id: "renewal_and_rent_increase", title: "Renewal terms & rent increase notice", category: "financial",
      keywords: ["renewal", "rent increase", "auto-renew", "automatically renew"], severity: "low", appliesTo: ["residential_lease"],
      detailed: "Check whether the lease auto-renews and how much notice you'd get before a rent increase.",
      simple: "Ask: does this renew on its own, and could rent go up?" },
    { id: "subletting_clause", title: "Subletting / assignment rights", category: "flexibility",
      keywords: ["sublet", "sublease", "assign this lease", "assignment"], severity: "low", appliesTo: ["residential_lease"],
      detailed: "Know whether you're allowed to sublet if you need to leave before the lease ends.",
      simple: "Ask: can I sublet if I need to move out early?" },
    { id: "waiver_of_rights", title: "Clauses waiving tenant legal rights", category: "legal_compliance",
      keywords: ["waives", "waiver of", "tenant agrees not to", "hold landlord harmless"], severity: "info", appliesTo: ["residential_lease"],
      detailed: "Broad waivers of legal rights are frequently unenforceable and worth flagging for a professional.",
      simple: "Flag: this may sign away rights you're not able to sign away." },
    { id: "notice_reason_stated", title: "Reason for the notice", category: "legal_compliance",
      keywords: ["for cause", "non-payment", "lease violation", "no-fault", "reason for termination"], severity: "high", appliesTo: ["notice_to_vacate"],
      detailed: "Notices with-cause and no-cause follow different rules and response timelines — confirm which this is.",
      simple: "Ask: why are they saying I have to leave?" },
    { id: "notice_response_deadline", title: "Deadline to respond or cure", category: "termination",
      keywords: ["days to cure", "days to vacate", "by the date", "deadline"], severity: "high", appliesTo: ["notice_to_vacate"],
      detailed: "Missing this deadline can waive your ability to contest the notice — confirm the exact date.",
      simple: "Ask: what's the exact date I need to respond by?" },
    { id: "original_lease_incorporated", title: "Original lease terms incorporated by reference", category: "legal_compliance",
      keywords: ["original lease", "master lease", "incorporated by reference"], severity: "medium", appliesTo: ["sublease"],
      detailed: "A sublease should reference and stay consistent with the original lease — ask to see that document too.",
      simple: "Ask: can I see the original lease this is based on?" },
    { id: "landlord_consent", title: "Landlord's written consent to sublet", category: "legal_compliance",
      keywords: ["landlord consent", "written consent", "approved by landlord"], severity: "high", appliesTo: ["sublease"],
      detailed: "Subletting without the landlord's required consent can be treated as a lease violation by the original tenant.",
      simple: "Ask: did the landlord actually approve this in writing?" }
  ];

  var TYPE_KEYWORDS = [
    ["notice_to_vacate", ["notice to vacate", "notice to quit", "termination of tenancy", "eviction notice"]],
    ["sublease", ["sublease", "sublessor", "sublessee", "subtenant"]],
    ["roommate_agreement", ["roommate agreement", "co-tenant agreement", "shared housing agreement"]],
    ["lease_addendum", ["addendum", "amendment to lease", "lease modification"]],
    ["residential_lease", ["lease agreement", "rental agreement", "landlord", "tenant", "leased premises"]]
  ];

  var STATE_NAMES = { "california": "CA", "new york": "NY", "texas": "TX", "florida": "FL", "illinois": "IL", "washington": "WA", "massachusetts": "MA", "georgia": "GA" };
  var STATE_PARAMS = {
    CA: { depositCapMonths: 2, note: "CA law caps deposits and sets a 21-day return window (illustrative — confirm current statute)." },
    NY: { depositCapMonths: 1, note: "NY caps deposits at one month's rent for most tenancies (illustrative)." },
    TX: { depositCapMonths: null, note: "TX has no statutory deposit cap, but return timelines still apply (illustrative)." }
  };

  var PII_PATTERNS = [
    { label: "email", re: /[\w.+-]+@[\w-]+\.[\w.-]+/g },
    { label: "phone", re: /\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g },
    { label: "ssn", re: /\b\d{3}-\d{2}-\d{4}\b/g },
    { label: "dob", re: /\b(?:DOB|Date of birth|Birth date|born on)[:\s]+(?:0[1-9]|1[0-2])[-/.](?:0[1-9]|[12]\d|3[01])[-/.](?:19|20)\d{2}\b/gi },
    { label: "ip_address", re: /\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b/g },
    { label: "street_address", re: /\b\d{1,5}\s+[A-Za-z0-9\.\s]{2,25}\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Court|Ct|Lane|Ln|Way)\b/gi }
  ];

  var ADVICE_PATTERNS = [/\bshould i\b/, /\bcan i sue\b/, /\bis this legal\b/, /\bis it legal\b/, /\bam i required\b/, /\bwhat should i do\b/, /\bcan they\b/, /\bis this enforceable\b/];

  var PRIORITY_LABEL = { high: "ask_before_signing", medium: "confirm_in_writing", low: "good_to_know", info: "good_to_know" };
  var PRIORITY_ORDER = { ask_before_signing: 0, confirm_in_writing: 1, good_to_know: 2 };
  var PRIORITY_TEXT = { ask_before_signing: "Ask before signing", confirm_in_writing: "Confirm in writing", good_to_know: "Good to know" };

  function redactPII(text) {
    var counts = {};
    var out = text;
    PII_PATTERNS.forEach(function (p) {
      out = out.replace(p.re, function () {
        counts[p.label] = (counts[p.label] || 0) + 1;
        return "[REDACTED_" + p.label.toUpperCase() + "]";
      });
    });
    return { text: out, counts: counts };
  }

  function classify(text) {
    var lowered = text.toLowerCase();
    var docType = "unknown", confidence = 0;
    for (var i = 0; i < TYPE_KEYWORDS.length; i++) {
      var hits = TYPE_KEYWORDS[i][1].filter(function (kw) { return lowered.indexOf(kw) !== -1; }).length;
      if (hits > 0) { docType = TYPE_KEYWORDS[i][0]; confidence = Math.min(1, 0.5 + 0.2 * hits); break; }
    }
    var jurisdiction = null;
    for (var name in STATE_NAMES) {
      if (lowered.indexOf(name) !== -1) { jurisdiction = STATE_NAMES[name]; break; }
    }
    return { docType: docType, confidence: confidence, jurisdiction: jurisdiction };
  }

  function getRubric(docType) {
    var applicable = RULES.filter(function (r) { return r.appliesTo.indexOf(docType) !== -1; });
    if (applicable.length === 0) applicable = RULES.filter(function (r) { return r.appliesTo.indexOf("residential_lease") !== -1; });
    return applicable;
  }

  function findExcerpt(original, lowered, keywords) {
    for (var i = 0; i < keywords.length; i++) {
      var idx = lowered.indexOf(keywords[i]);
      if (idx !== -1) {
        var start = Math.max(0, idx - 50), end = Math.min(original.length, idx + keywords[i].length + 70);
        return original.slice(start, end).trim();
      }
    }
    return null;
  }

  function extractClauses(text, rubricRules, jurisdiction, plainMode) {
    var lowered = text.toLowerCase();
    return rubricRules.map(function (rule) {
      var excerpt = findExcerpt(text, lowered, rule.keywords);
      var present = excerpt !== null;
      var guidance = plainMode ? rule.simple : rule.detailed;
      var stateNote = (!present && jurisdiction && STATE_PARAMS[jurisdiction]) ? (" Note for " + jurisdiction + ": " + STATE_PARAMS[jurisdiction].note) : "";
      return {
        ruleId: rule.id, title: rule.title, category: rule.category, present: present,
        severity: present ? "info" : rule.severity,
        excerpt: excerpt,
        explanation: (present ? "Found language addressing this. " : "No matching language found in the document. ") + guidance + stateNote
      };
    });
  }

  function computeTenantProtectionScore(findings, rubricRules) {
    var weights = { high: 3, medium: 2, low: 1, info: 1 };
    var totalWeight = 0, earnedWeight = 0;
    var catTotals = {}, catEarned = {};
    findings.forEach(function (f) {
      var rule = rubricRules.find(function (r) { return r.id === f.ruleId; });
      var sev = (rule && rule.severity) || "medium";
      var cat = (rule && rule.category) || "general";
      var w = weights[sev] || 1;
      totalWeight += w;
      catTotals[cat] = (catTotals[cat] || 0) + w;
      if (f.present) {
        earnedWeight += w;
        catEarned[cat] = (catEarned[cat] || 0) + w;
      } else {
        catEarned[cat] = catEarned[cat] || 0;
      }
    });
    var overall = totalWeight > 0 ? Math.round((earnedWeight / totalWeight) * 100) : 100;
    var cats = {};
    for (var c in catTotals) {
      cats[c] = Math.round(((catEarned[c] || 0) / catTotals[c]) * 100);
    }
    return { overall: overall, categories: cats };
  }

  function generateConsultationBrief(doc) {
    var docType = typeLabel(doc.classification.docType);
    var jur = doc.classification.jurisdiction || "General / Multi-State";
    var lines = [
      "# Legal Consultation Brief & Tenant Advocacy Packet",
      "**Generated by LeaseLens for Tenant Consultation** | *Confidential Tenant Intake Document*",
      "",
      "## 1. Document Overview",
      "- **Document Type:** " + docType + " (Confidence: " + Math.round(doc.classification.confidence * 100) + "%)",
      "- **Jurisdiction:** " + jur,
      "- **Tenant Protection Score:** " + doc.score.overall + " / 100",
      "",
      "## 2. Plain-Language Summary",
      doc.summary,
      "",
      "## 3. Category Breakdown"
    ];
    for (var c in doc.score.categories) {
      lines.push("- **" + c.replace("_", " ").toUpperCase() + ":** " + doc.score.categories[c] + "% coverage");
    }
    lines.push("", "## 4. Critical Missing Protections & Red Flags (Ask Before Signing)");
    var highs = doc.findings.filter(function (f) { return !f.present && f.severity === "high"; });
    if (highs.length) {
      highs.forEach(function (f) { lines.push("- **" + f.title + ":** " + f.explanation); });
    } else {
      lines.push("- No high-severity missing protections detected.");
    }
    lines.push("", "## 5. Items to Confirm in Writing");
    var meds = doc.findings.filter(function (f) { return !f.present && f.severity === "medium"; });
    if (meds.length) {
      meds.forEach(function (f) { lines.push("- **" + f.title + ":** " + f.explanation); });
    } else {
      lines.push("- No medium-severity ambiguities detected.");
    }
    lines.push(
      "",
      "## 6. Recommended Questions for Legal Professional / Clinic",
      "1. Does state or municipal tenant protection law imply any mandatory warranty of habitability terms that this document omitted?",
      "2. Are the specific dispute resolution, fee structures, or notice windows listed legally enforceable in this jurisdiction?",
      "3. If any early termination or sublease restriction applies, what are the tenant's statutory rights to mitigate damages?",
      "",
      "## 7. Important Disclaimer",
      "This packet provides document organization and informational analysis, not formal legal advice. Tenancy laws, municipal rent boards, and court precedents vary by local city/county jurisdiction. Consult a licensed attorney or certified tenant rights advocacy organization for formal representation."
    );
    return lines.join("\n");
  }

  function chunkText(text) {
    return text.split(/\n+/).map(function (p) { return p.trim(); }).filter(Boolean);
  }

  var STOPWORDS = { the:1, a:1, an:1, is:1, are:1, was:1, were:1, how:1, what:1, when:1, where:1, before:1, after:1, much:1, many:1, does:1, do:1, did:1, can:1, will:1, would:1, this:1, that:1, and:1, for:1, with:1, about:1, from:1 };

  function tokenize(s) { return (s.toLowerCase().match(/[a-z0-9']+/g) || []); }

  function retrieveChunks(question, chunks, topK) {
    var qTerms = {};
    tokenize(question).forEach(function (t) { qTerms[t] = true; });
    var scored = chunks.map(function (c) {
      var terms = tokenize(c);
      var overlap = terms.filter(function (t) { return qTerms[t]; }).length;
      return { chunk: c, score: overlap / (terms.length + 1) };
    }).filter(function (s) { return s.score > 0; });
    scored.sort(function (a, b) { return b.score - a.score; });
    return scored.slice(0, topK || 4).map(function (s) { return s.chunk; });
  }

  function bestWindow(chunk, qTerms) {
    var meaningful = Object.keys(qTerms).filter(function (t) { return !STOPWORDS[t] && t.length >= 3; });
    if (meaningful.length === 0) meaningful = Object.keys(qTerms);
    var sentences = chunk.split(/(?<=[.!?])\s+/).filter(Boolean);
    if (sentences.length === 0) return chunk.slice(0, 220);
    var best = sentences[0], bestScore = -1;
    sentences.forEach(function (s) {
      var lowered = s.toLowerCase();
      var score = meaningful.filter(function (t) { return lowered.indexOf(t) !== -1; }).length;
      if (score > bestScore) { bestScore = score; best = s; }
    });
    if (bestScore <= 0) return chunk.slice(0, 220).trim();
    return best.trim();
  }

  function answerQuestion(text, question) {
    var chunks = chunkText(text);
    var relevant = retrieveChunks(question, chunks, 3);
    var isAdvice = ADVICE_PATTERNS.some(function (re) { return re.test(question.toLowerCase()); });
    var disclaimer = isAdvice ? "This is general information based on your document, not legal advice. For guidance specific to your situation, consider a tenant rights clinic or a licensed attorney in your state." : null;

    if (relevant.length === 0) {
      return { answer: "I couldn't find anything in this document that addresses that question. It may not be covered here, or try rephrasing.", grounded: false, citations: [], disclaimer: disclaimer };
    }
    var qTerms = {};
    tokenize(question).forEach(function (t) { qTerms[t] = true; });
    var windows = relevant.map(function (c) { return bestWindow(c, qTerms); });
    return { answer: "Based on this document: " + windows.join(" (…) "), grounded: true, citations: windows, disclaimer: disclaimer };
  }

  function generateChecklist(findings) {
    var items = findings.filter(function (f) { return !f.present; }).map(function (f) {
      return { priority: PRIORITY_LABEL[f.severity] || "good_to_know", text: f.title + ": " + f.explanation };
    });
    items.push({ priority: "good_to_know", text: "Bring this checklist and the original document to a tenant rights clinic or attorney if any 'ask before signing' item isn't resolved to your satisfaction." });
    items.sort(function (a, b) { return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]; });
    return items;
  }

  function compareFindings(findingsA, findingsB) {
    var byIdB = {};
    findingsB.forEach(function (f) { byIdB[f.ruleId] = f; });
    var diffs = [];
    findingsA.forEach(function (fa) {
      var fb = byIdB[fa.ruleId];
      if (!fb) return;
      var sa = fa.present ? "present" : "absent", sb = fb.present ? "present" : "absent";
      diffs.push({ ruleId: fa.ruleId, title: fa.title, statusA: sa, statusB: sb, changed: sa !== sb });
    });
    return diffs;
  }

  function plainSummary(findings) {
    var presentCount = findings.filter(function (f) { return f.present; }).length;
    var missing = findings.filter(function (f) { return !f.present && (f.severity === "high" || f.severity === "medium"); });
    var s = "This document covers " + presentCount + " of " + findings.length + " common items checked. ";
    s += missing.length ? ("Worth asking about before you sign: " + missing.slice(0, 3).map(function (f) { return f.title; }).join("; ") + ".")
                         : "The common items checked for all appear to be addressed somewhere in the text.";
    return s;
  }

  /* =========================================================================
     UI WIRING
     ========================================================================= */

  var el = function (id) { return document.getElementById(id); };
  var state = { mode: "analyze", plain: false, docA: null, docB: null, activeTab: "findings" };

  function safeGet(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function safeSet(key, val) { try { localStorage.setItem(key, val); } catch (e) { /* ignore */ } }

  // --- Accessibility controls ---
  var scale = parseFloat(safeGet("ll_scale")) || 1;
  document.documentElement.style.setProperty("--scale", scale);
  function applyContrast(on) { document.body.setAttribute("data-contrast", on ? "high" : "normal"); el("contrastToggle").setAttribute("aria-pressed", on ? "true" : "false"); }
  applyContrast(safeGet("ll_contrast") === "1");
  el("fontUp").addEventListener("click", function () { scale = Math.min(1.4, scale + 0.1); document.documentElement.style.setProperty("--scale", scale); safeSet("ll_scale", scale); });
  el("fontDown").addEventListener("click", function () { scale = Math.max(0.85, scale - 0.1); document.documentElement.style.setProperty("--scale", scale); safeSet("ll_scale", scale); });
  el("contrastToggle").addEventListener("click", function () { var on = el("contrastToggle").getAttribute("aria-pressed") !== "true"; applyContrast(on); safeSet("ll_contrast", on ? "1" : "0"); });
  el("plainToggle").addEventListener("click", function () {
    state.plain = !state.plain;
    el("plainToggle").setAttribute("aria-pressed", state.plain ? "true" : "false");
    if (state.docA) runAnalysis();
  });

  // --- Voice / Audio Assistance (Web Speech API) ---
  var speaking = false;
  function speakText(textToSpeak, buttonEl) {
    if (!('speechSynthesis' in window)) {
      showToast("Speech synthesis is not supported in this browser.");
      return;
    }
    if (speaking) {
      window.speechSynthesis.cancel();
      speaking = false;
      if (buttonEl) buttonEl.textContent = "🔊 Read Aloud";
      var vt = el("voiceToggle");
      if (vt) { vt.setAttribute("aria-pressed", "false"); vt.textContent = "🔊 Read Aloud"; }
      announce("Audio playback stopped.");
      return;
    }
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.onend = function() {
      speaking = false;
      if (buttonEl) buttonEl.textContent = "🔊 Read Aloud";
      var vt = el("voiceToggle");
      if (vt) { vt.setAttribute("aria-pressed", "false"); vt.textContent = "🔊 Read Aloud"; }
      announce("Finished reading aloud.");
    };
    utterance.onerror = function() {
      speaking = false;
      if (buttonEl) buttonEl.textContent = "🔊 Read Aloud";
      var vt = el("voiceToggle");
      if (vt) { vt.setAttribute("aria-pressed", "false"); vt.textContent = "🔊 Read Aloud"; }
    };
    speaking = true;
    if (buttonEl) buttonEl.textContent = "⏹️ Stop Audio";
    var vt2 = el("voiceToggle");
    if (vt2) { vt2.setAttribute("aria-pressed", "true"); vt2.textContent = "⏹️ Stop Audio"; }
    announce("Reading summary and key findings aloud.");
    window.speechSynthesis.speak(utterance);
  }

  el("voiceToggle").addEventListener("click", function () {
    if (!state.docA) {
      showToast("Analyze a document first, then click Read Aloud.");
      return;
    }
    var spoken = state.docA.summary;
    var highRisks = state.docA.findings.filter(function (f) { return !f.present && f.severity === "high"; });
    if (highRisks.length > 0) {
      spoken += " Important missing protections: " + highRisks.map(function (f) { return f.title; }).join(", ") + ".";
    }
    speakText(spoken, el("voiceToggle"));
  });

  // --- Sample documents ---
  var SAMPLES = {
    lease: "RESIDENTIAL LEASE AGREEMENT\n\nThis lease is entered into between the Landlord and Tenant for the premises located in the State of California.\n\n1. RENT. Tenant agrees to pay $2,400 per month. Rent is due on the 1st of each month. A late fee of $75 applies after a 3-day grace period.\n\n2. SECURITY DEPOSIT. Tenant shall pay a security deposit of $2,400, to be returned within 21 days of move-out, less lawful deductions.\n\n3. MAINTENANCE. Landlord is responsible for maintaining the premises in a habitable condition. Tenant is responsible for minor repairs under $50.\n\n4. ENTRY. Landlord shall provide at least 24 hours notice to enter the premises except in emergencies.\n\n5. TERMINATION. Tenant may terminate this lease early by paying a fee equal to two months' rent.",
    "lease-alt": "RESIDENTIAL LEASE AGREEMENT\n\nThis lease is entered into between the Landlord and Tenant for the premises located in the State of California.\n\n1. RENT. Tenant agrees to pay $2,600 per month. Rent is due on the 1st of each month.\n\n2. SECURITY DEPOSIT. Tenant shall pay a security deposit of $2,600, to be returned within 21 days of move-out.\n\n3. MAINTENANCE. Landlord is responsible for maintaining the premises in a habitable condition.\n\n5. TERMINATION. Tenant may terminate this lease early by paying a fee equal to two months' rent.",
    notice: "NOTICE TO VACATE\n\nThis notice to vacate is served for non-payment of rent. Tenant has 3 days to cure by paying the outstanding balance, or must vacate by the date listed below: March 15.",
    sublease: "SUBLEASE AGREEMENT\n\nThis sublease is entered into between Sublessor and Sublessee for the remaining term of the original lease, which is incorporated by reference. The sublessor has obtained written consent from the landlord to sublet."
  };
  document.querySelectorAll(".sample-buttons button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var key = btn.getAttribute("data-sample"), target = btn.getAttribute("data-target");
      el(target === "A" ? "docA" : "docB").value = SAMPLES[key];
    });
  });

  el("fileA").addEventListener("change", function (e) { readFile(e, "docA", "fileANote"); });
  el("fileB").addEventListener("change", function (e) { readFile(e, "docB", "fileBNote"); });
  function readFile(e, targetId, noteId) {
    var file = e.target.files[0];
    if (!file) return;
    if (file.size > 16 * 1024 * 1024) { el(noteId).textContent = "File too large (16 MB max)."; return; }

    var ext = file.name.split('.').pop().toLowerCase();
    el(noteId).textContent = "Loading " + file.name + "…";

    if (ext === "pdf" && window.pdfjsLib) {
      var fileReader = new FileReader();
      fileReader.onload = function () {
        var typedarray = new Uint8Array(this.result);
        pdfjsLib.getDocument(typedarray).promise.then(function (pdf) {
          var maxPages = Math.min(pdf.numPages, 10);
          var pagePromises = [];
          for (var i = 1; i <= maxPages; i++) {
            pagePromises.push(pdf.getPage(i).then(function (page) {
              return page.getTextContent().then(function (tc) {
                return tc.items.map(function (s) { return s.str; }).join(" ");
              });
            }));
          }
          Promise.all(pagePromises).then(function (texts) {
            var combined = texts.join("\n\n").trim();
            if (combined.length > 20) {
              el(targetId).value = combined;
              el(noteId).textContent = file.name + " (" + pdf.numPages + " page" + (pdf.numPages > 1 ? "s" : "") + ") extracted.";
              announce(file.name + " extracted.");
            } else {
              el(noteId).textContent = file.name + " (Scanned PDF: start API backend for OCR / Vision extraction).";
            }
          });
        }).catch(function (err) {
          el(noteId).textContent = "Could not parse PDF: " + err.message;
        });
      };
      fileReader.readAsArrayBuffer(file);
    } else if (["png", "jpg", "jpeg", "webp"].indexOf(ext) !== -1) {
      var apiBase = (window.location.protocol === "file:" || window.location.origin === "null") ? "http://localhost:8000" : "";
      el(noteId).textContent = "Uploading " + file.name + " for photo transcription…";
      // Attempt backend transcription
      fetch(apiBase + "/api/session", { method: "POST" })
        .then(function (res) { return res.json(); })
        .then(function (sessionData) {
          var form = new FormData();
          form.append("file", file);
          return fetch(apiBase + "/api/documents", {
            method: "POST",
            headers: { "Authorization": "Bearer " + sessionData.access_token },
            body: form
          });
        })
        .then(function (res) {
          if (!res.ok) throw new Error("Upload failed");
          return res.json();
        })
        .then(function (docData) {
          el(noteId).textContent = file.name + " transcribed successfully via API!";
          announce("Photo transcribed successfully.");
          // Also fetch analysis
          fetch(apiBase + "/api/documents/" + docData.document_id + "/analyze", {
            method: "POST",
            headers: { "Authorization": "Bearer " + docData.document_id } // session
          }).catch(function () {});
        })
        .catch(function () {
          el(noteId).textContent = file.name + " loaded. (For auto-transcription, start backend: uvicorn app.main:app)";
          announce("Photo selected. Run backend for automatic OCR/vision.");
        });
    } else {
      var reader = new FileReader();
      reader.onload = function () {
        el(targetId).value = reader.result;
        el(noteId).textContent = file.name + " loaded.";
        announce(file.name + " loaded.");
      };
      reader.readAsText(file);
    }
  }

  // --- Mode switch ---
  el("modeAnalyze").addEventListener("click", function () { setMode("analyze"); });
  el("modeCompare").addEventListener("click", function () { setMode("compare"); });
  function setMode(mode) {
    state.mode = mode;
    el("modeAnalyze").setAttribute("aria-pressed", mode === "analyze" ? "true" : "false");
    el("modeCompare").setAttribute("aria-pressed", mode === "compare" ? "true" : "false");
    el("docSlotB").hidden = mode !== "compare";
    el("inputGrid").className = "input-grid " + (mode === "compare" ? "" : "single");
    el("slotALabel").textContent = mode === "compare" ? "First document" : "Your document";
    el("results").hidden = true;
  }

  // --- Analyze ---
  el("analyzeBtn").addEventListener("click", runAnalysis);

  function announce(msg) {
    var a = el("liveAnnounce");
    if (a) {
      a.textContent = "";
      setTimeout(function () { a.textContent = msg; }, 50);
    }
  }

  function showToast(msg) {
    var existing = document.querySelector(".toast");
    if (existing) existing.remove();
    var t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    t.setAttribute("role", "alert");
    document.body.appendChild(t);
    setTimeout(function () {
      t.style.opacity = "0";
      setTimeout(function () { t.remove(); }, 300);
    }, 2500);
  }

  function analyzeOne(rawText) {
    var redaction = redactPII(rawText);
    var text = redaction.text;
    var classification = classify(text);
    var rubric = getRubric(classification.docType);
    var findings = extractClauses(text, rubric, classification.jurisdiction, state.plain);
    var score = computeTenantProtectionScore(findings, rubric);
    return { text: text, classification: classification, findings: findings, score: score, redactionCounts: redaction.counts, summary: plainSummary(findings) };
  }

  function runAnalysis() {
    var rawA = el("docA").value.trim();
    if (!rawA) { el("docA").focus(); return; }
    state.docA = analyzeOne(rawA);
    state.docB = null;
    if (state.mode === "compare") {
      var rawB = el("docB").value.trim();
      if (rawB) state.docB = analyzeOne(rawB);
    }
    state.thread = [];
    renderResults();
    announce("Analysis complete for " + typeLabel(state.docA.classification.docType) + ". Tenant protection score: " + state.docA.score.overall + " out of 100.");
  }

  function typeLabel(t) {
    return { residential_lease: "Residential lease", notice_to_vacate: "Notice to vacate", sublease: "Sublease",
             roommate_agreement: "Roommate agreement", lease_addendum: "Lease addendum", unknown: "Unclassified document" }[t] || t;
  }

  function renderResults() {
    el("results").hidden = false;
    var strip = el("contextStrip");
    strip.innerHTML = "";
    addBadge(strip, typeLabel(state.docA.classification.docType));
    if (state.docA.classification.jurisdiction) addBadge(strip, "Jurisdiction: " + state.docA.classification.jurisdiction);
    var redactedTotal = Object.values(state.docA.redactionCounts).reduce(function (a, b) { return a + b; }, 0);
    if (redactedTotal > 0) addBadge(strip, redactedTotal + " personal identifier" + (redactedTotal > 1 ? "s" : "") + " masked", true);

    var scoreContainer = el("scoreContainer");
    if (scoreContainer && state.docA && state.docA.score) {
      var sc = state.docA.score;
      var levelClass = sc.overall >= 80 ? "high" : (sc.overall >= 50 ? "medium" : "low");
      var levelLabel = sc.overall >= 80 ? "Strong Protection" : (sc.overall >= 50 ? "Moderate Protection" : "High Risk / Review Needed");
      var html = '<div class="score-card">' +
        '<div class="score-main">' +
          '<div class="score-dial ' + levelClass + '">' + sc.overall + '</div>' +
          '<div class="score-text">' +
            '<h3>Tenant Protection Score: ' + sc.overall + '/100 (' + levelLabel + ')</h3>' +
            '<p>Contextual assessment of essential tenant rights and risk clauses in this document.</p>' +
          '</div>' +
        '</div>' +
        '<div class="score-categories">';
      for (var cat in sc.categories) {
        html += '<span class="cat-pill">' + cat.replace('_', ' ').toUpperCase() + ': ' + sc.categories[cat] + '%</span>';
      }
      html += '</div></div>';
      scoreContainer.innerHTML = html;
    }

    var tabs = [["findings", "Findings"], ["checklist", "Checklist"], ["ask", "Ask"]];
    if (state.mode === "compare" && state.docB) tabs.push(["compare", "Compare"]);

    var tabList = el("tabList");
    tabList.innerHTML = "";
    tabs.forEach(function (t, i) {
      var b = document.createElement("button");
      b.className = "tab"; b.setAttribute("role", "tab"); b.id = "tab-" + t[0];
      b.setAttribute("aria-selected", state.activeTab === t[0] ? "true" : "false");
      b.setAttribute("aria-controls", "panel-" + t[0]);
      b.textContent = t[1];
      b.addEventListener("click", function () { state.activeTab = t[0]; renderResults(); });
      tabList.appendChild(b);
    });
    if (!tabs.some(function (t) { return t[0] === state.activeTab; })) state.activeTab = "findings";

    var panels = el("tabPanels");
    panels.innerHTML = "";
    var panelWrap = document.createElement("div");
    panelWrap.id = "panel-" + state.activeTab;
    panelWrap.setAttribute("role", "tabpanel");
    panelWrap.setAttribute("aria-labelledby", "tab-" + state.activeTab);

    if (state.activeTab === "findings") renderFindings(panelWrap);
    else if (state.activeTab === "checklist") renderChecklist(panelWrap);
    else if (state.activeTab === "ask") renderAsk(panelWrap);
    else if (state.activeTab === "compare") renderCompare(panelWrap);

    panels.appendChild(panelWrap);
  }

  function addBadge(container, text, redacted) {
    var b = document.createElement("span");
    b.className = "badge" + (redacted ? " redacted" : "");
    b.textContent = text;
    container.appendChild(b);
  }

  function renderFindings(container) {
    var summaryWrap = document.createElement("div");
    summaryWrap.className = "summary-box";
    var summary = document.createElement("p");
    summary.style.margin = "0 0 0.7rem 0";
    summary.textContent = state.docA.summary;
    summaryWrap.appendChild(summary);

    var voiceBtn = document.createElement("button");
    voiceBtn.className = "btn-secondary";
    voiceBtn.style.fontSize = "0.8rem";
    voiceBtn.style.padding = "0.35rem 0.75rem";
    voiceBtn.textContent = speaking ? "⏹️ Stop Audio" : "🔊 Listen to Summary";
    voiceBtn.setAttribute("aria-label", "Listen to this plain-language summary aloud");
    voiceBtn.addEventListener("click", function () {
      speakText(state.docA.summary, voiceBtn);
    });
    summaryWrap.appendChild(voiceBtn);
    container.appendChild(summaryWrap);

    var list = document.createElement("ul");
    list.className = "finding-list";
    state.docA.findings.forEach(function (f) {
      var li = document.createElement("li");
      li.className = "finding"; li.setAttribute("data-severity", f.severity);
      var head = document.createElement("div"); head.className = "finding-head";
      var title = document.createElement("span"); title.className = "finding-title"; title.textContent = f.title;
      var pill = document.createElement("span");
      pill.className = "status-pill " + (f.present ? "present" : "absent-" + f.severity);
      pill.textContent = f.present ? "Addressed" : ("Missing — " + f.severity);
      head.appendChild(title); head.appendChild(pill);
      li.appendChild(head);
      var explain = document.createElement("p"); explain.className = "finding-explain"; explain.textContent = f.explanation;
      li.appendChild(explain);
      if (f.excerpt) {
        var ex = document.createElement("p"); ex.className = "finding-excerpt"; ex.textContent = "\u201C…" + f.excerpt + "…\u201D";
        li.appendChild(ex);
      }
      list.appendChild(li);
    });
    container.appendChild(list);
  }

  function renderChecklist(container) {
    var items = generateChecklist(state.docA.findings);
    var list = document.createElement("ul"); list.className = "checklist-list";
    items.forEach(function (item) {
      var li = document.createElement("li"); li.className = "checklist-item"; li.setAttribute("data-priority", item.priority);
      var tag = document.createElement("span"); tag.className = "tag"; tag.textContent = PRIORITY_TEXT[item.priority];
      var text = document.createElement("span"); text.textContent = item.text;
      li.appendChild(tag); li.appendChild(text);
      list.appendChild(li);
    });
    container.appendChild(list);

    var actions = document.createElement("div"); actions.className = "checklist-actions";

    var dlBrief = document.createElement("button"); dlBrief.className = "btn-primary"; dlBrief.textContent = "Download Legal Aid Brief (.md)";
    dlBrief.addEventListener("click", function () {
      var briefMd = generateConsultationBrief(state.docA);
      var blob = new Blob([briefMd], { type: "text/markdown" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "tenant-defense-brief.md";
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      showToast("Downloaded legal consultation packet.");
      announce("Downloaded legal consultation packet.");
    });
    actions.appendChild(dlBrief);

    var voiceChecklist = document.createElement("button");
    voiceChecklist.className = "btn-secondary";
    voiceChecklist.textContent = "🔊 Read Checklist";
    voiceChecklist.setAttribute("aria-label", "Listen to action checklist aloud");
    voiceChecklist.addEventListener("click", function () {
      var spokenList = items.map(function (i) { return PRIORITY_TEXT[i.priority] + ": " + i.text; }).join(". ");
      speakText("Your prioritized action checklist: " + spokenList, voiceChecklist);
    });
    actions.appendChild(voiceChecklist);

    var copyBtn = document.createElement("button"); copyBtn.className = "btn-secondary"; copyBtn.textContent = "Copy Checklist";
    copyBtn.addEventListener("click", function () {
      var lines = items.map(function (i) { return "[" + PRIORITY_TEXT[i.priority] + "] " + i.text; });
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(lines.join("\n\n")).then(function () {
          showToast("Checklist copied to clipboard.");
          announce("Checklist copied to clipboard.");
        });
      } else {
        showToast("Checklist copied to clipboard.");
      }
    });
    actions.appendChild(copyBtn);

    var dl = document.createElement("button"); dl.className = "btn-secondary"; dl.textContent = "Download as text";
    dl.addEventListener("click", function () {
      var lines = items.map(function (i) { return "[" + PRIORITY_TEXT[i.priority] + "] " + i.text; });
      var blob = new Blob([lines.join("\n\n")], { type: "text/plain" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "leaselens-checklist.txt";
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    });
    actions.appendChild(dl);
    container.appendChild(actions);
  }

  function renderAsk(container) {
    var thread = document.createElement("div"); thread.className = "ask-thread"; thread.id = "askThread";
    (state.thread || []).forEach(function (m) { thread.appendChild(renderMsg(m)); });
    container.appendChild(thread);

    var form = document.createElement("form"); form.className = "ask-form";
    var input = document.createElement("input"); input.type = "text"; input.placeholder = "e.g. how much notice before entry?";
    input.setAttribute("aria-label", "Ask a question about this document");
    var submit = document.createElement("button"); submit.type = "submit"; submit.className = "btn-primary"; submit.textContent = "Ask";
    form.appendChild(input); form.appendChild(submit);
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = input.value.trim();
      if (!q) return;
      state.thread = state.thread || [];
      state.thread.push({ role: "user", text: q });
      var result = answerQuestion(state.docA.text, q);
      state.thread.push({ role: "assistant", text: result.answer, disclaimer: result.disclaimer, citations: result.grounded ? [] : [] });
      input.value = "";
      renderResults();
      var t = el("askThread"); if (t) t.scrollTop = t.scrollHeight;
    });
    container.appendChild(form);
  }

  function renderMsg(m) {
    var div = document.createElement("div"); div.className = "msg " + m.role;
    div.textContent = m.text;
    if (m.disclaimer) { var d = document.createElement("span"); d.className = "disclaimer"; d.textContent = m.disclaimer; div.appendChild(d); }
    return div;
  }

  function renderCompare(container) {
    var diffs = compareFindings(state.docA.findings, state.docB.findings);
    if (diffs.length === 0) {
      var empty = document.createElement("p"); empty.className = "empty-state"; empty.textContent = "These documents were classified differently enough that there's no shared checklist to compare.";
      container.appendChild(empty); return;
    }
    var table = document.createElement("table"); table.className = "compare-table";
    table.innerHTML = "<thead><tr><th>Item</th><th>Document A</th><th>Document B</th><th>Status</th></tr></thead>";
    var tbody = document.createElement("tbody");
    diffs.forEach(function (d) {
      var tr = document.createElement("tr");
      tr.innerHTML = "<td>" + d.title + "</td><td>" + d.statusA + "</td><td>" + d.statusB + "</td>" +
        "<td><span class=\"diff-flag " + (d.changed ? "changed" : "same") + "\">" + (d.changed ? "Differs" : "Same") + "</span></td>";
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }
})();
