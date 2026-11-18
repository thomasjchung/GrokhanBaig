const flyer = document.querySelector("#flyer");
const results = document.querySelector("#results");
const watch = document.querySelector("#watch");
const note = document.querySelector("#check-note");
const today = document.querySelector("#today");
const search = document.querySelector("#q");
const gmailLink = document.querySelector("#gmail");
let focus = null;
let gsuitePopup = null;
let gsuiteDone = false;
let gsuiteStarting = false;

today.textContent = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
}).format(new Date());

function whenLabel(iso) {
  if (!iso) return "Date still on the post";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function accountBlock(account) {
  const wrap = document.createElement("article");
  wrap.className = account.watching ? "account" : "result";
  const text = document.createElement("div");
  if (focus === account.username) wrap.classList.add("selected");
  const title = document.createElement("button");
  title.type = "button";
  title.className = "pick";
  title.textContent = account.display_name;
  title.addEventListener("click", () => {
    focus = focus === account.username ? null : account.username;
    refresh(false);
  });
  const handle = document.createElement("p");
  handle.className = "handle";
  const link = document.createElement("a");
  const isMail = account.provider === "email";
  link.href = isMail ? "mailto:" + account.email : account.instagram_url;
  link.textContent = isMail ? account.email : "@" + account.username;
  if (!isMail) {
    link.target = "_blank";
    link.rel = "noreferrer";
  }
  handle.append(link);
  if (account.upcoming_count) {
    const count = document.createElement("p");
    count.className = "handle";
    count.textContent = account.upcoming_count + " upcoming";
    handle.append(count);
  }
  text.append(title, handle);
  if (account.bio) {
    const bio = document.createElement("p");
    bio.className = "bio";
    bio.textContent = account.bio;
    text.append(bio);
  }
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = account.watching ? "Watching" : "Watch";
  if (account.watching) button.classList.add("watching");
  button.addEventListener("click", async () => {
    if (account.watching) {
      await fetch("/api/me/follows/" + account.username, { method: "DELETE" });
    } else {
      await fetch("/api/me/follows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: account.username }),
      });
    }
    await refresh();
  });
  wrap.append(text, button);
  return wrap;
}

function renderFlyer(events) {
  flyer.replaceChildren();
  if (!events.length) {
    flyer.classList.add("empty");
    const when = document.createElement("p");
    when.className = "when";
    when.textContent = today.textContent;
    const title = document.createElement("h1");
    title.textContent = "No show on the sheet";
    const place = document.createElement("p");
    place.className = "place";
    const pin = document.createElement("span");
    pin.className = "pin";
    place.append(pin, document.createTextNode("New Haven"));
    const row = document.createElement("div");
    row.className = "stamp-row";
    const stamp = document.createElement("button");
    stamp.className = "stamp";
    stamp.type = "button";
    stamp.disabled = true;
    stamp.textContent = "RSVP";
    const who = document.createElement("div");
    who.className = "who";
    const org = document.createElement("p");
    org.className = "organizer";
    org.textContent = "Farhan and Tommy Club";
    who.append(org);
    row.append(stamp, who);
    const facts = document.createElement("dl");
    facts.className = "facts";
    const pairs = [
      ["Name", "Waiting on a new post"],
      ["Where", "New Haven"],
      ["Instagram", "https://www.instagram.com/farhanandtommyclub/"],
    ];
    for (const [label, value] of pairs) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      if (value.startsWith("http")) {
        const a = document.createElement("a");
        a.href = value;
        a.textContent = "@farhanandtommyclub";
        dd.append(a);
      } else {
        dd.textContent = value;
      }
      facts.append(dt, dd);
    }
    flyer.append(when, title, place, row, facts);
    return;
  }
  flyer.classList.remove("empty");
  const event = events[0];
  const when = document.createElement("p");
  when.className = "when";
  when.textContent = whenLabel(event.starts_at);
  const title = document.createElement("h1");
  title.textContent = event.name;
  const place = document.createElement("p");
  place.className = "place";
  const pin = document.createElement("span");
  pin.className = "pin";
  place.append(pin, document.createTextNode(event.location_name || "New Haven"));
  flyer.append(when, title, place);
  if (event.image_url) {
    const img = document.createElement("img");
    img.className = "hero";
    img.alt = "";
    img.src = event.image_url;
    flyer.append(img);
  }
  const row = document.createElement("div");
  row.className = "stamp-row";
  const stamp = document.createElement("button");
  stamp.className = "stamp";
  stamp.type = "button";
  const going = event.rsvp.status === "going";
  stamp.textContent = going ? "Going" : "RSVP";
  stamp.setAttribute("aria-pressed", going ? "true" : "false");
  stamp.addEventListener("click", async () => {
    await fetch("/api/events/" + event.id + "/rsvp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: going ? "none" : "going" }),
    });
    await refresh(false);
  });
  const who = document.createElement("div");
  who.className = "who";
  const org = document.createElement("p");
  org.className = "organizer";
  org.textContent = event.organizer.name || "Club";
  who.append(org);
  if (event.rsvp.going_count > 0) {
    const count = document.createElement("p");
    count.textContent = event.rsvp.going_count + " going";
    const faces = document.createElement("div");
    faces.className = "faces";
    const face = document.createElement("span");
    face.className = "face";
    face.textContent = "Y";
    faces.append(face);
    who.append(count, faces);
  }
  row.append(stamp, who);
  const facts = document.createElement("dl");
  facts.className = "facts";
  const rows = [
    ["Name", event.name],
    ["Where", event.location_name || "New Haven"],
    ["Line", event.tagline || event.description || ""],
    ["Instagram", event.links.instagram || ""],
    ["Partiful", event.links.partiful || ""],
  ];
  for (const [label, value] of rows) {
    if (!value) continue;
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    if (String(value).startsWith("http")) {
      const a = document.createElement("a");
      a.href = value;
      a.target = "_blank";
      a.rel = "noreferrer";
      a.textContent = value
        .replace(/^https?:\/\/(www\.)?instagram\.com\//, "@")
        .replace(/\/$/, "")
        .replace(/^https?:\/\//, "");
      dd.append(a);
    } else {
      dd.textContent = value;
    }
    facts.append(dt, dd);
  }
  flyer.append(row, facts);
  if (events.length > 1) {
    const more = document.createElement("p");
    more.className = "organizer";
    const sourceName = event.source && event.source.name;
    const same = [];
    const other = [];
    for (const item of events.slice(1)) {
      const itemSource = item.source && item.source.name;
      if (sourceName && itemSource === sourceName) same.push(item.name);
      else other.push(itemSource ? item.name + " · " + itemSource : item.name);
    }
    const bits = [];
    if (same.length) bits.push("Also from " + sourceName + ": " + same.join(", "));
    if (other.length) bits.push(other.join(", "));
    more.textContent = bits.join(". ");
    flyer.append(more);
  }
}

async function refresh(runCheck) {
  if (runCheck) {
    note.textContent = "Checking accounts on your list…";
    const checked = await fetch("/api/checks", { method: "POST" }).then((res) => res.json());
    const line = (checked.accounts || []).map((item) => item.detail).join(" ");
    note.textContent = line || "Nothing to check.";
  }
  const [events, follows, found] = await Promise.all([
    fetch("/api/events").then((res) => res.json()),
    fetch("/api/me/follows").then((res) => res.json()),
    fetch("/api/accounts?q=" + encodeURIComponent(search.value.trim())).then((res) => res.json()),
  ]);
  const all = events.events || [];
  const visible = focus
    ? all.filter((item) => item.source && item.source.username === focus)
    : all;
  renderFlyer(visible);
  const gmail = await fetch("/api/gmail").then((res) => res.json());
  gmailLink.textContent = gmail.connected ? gmail.email : "Connect Gmail";
  watch.replaceChildren();
  for (const account of follows.accounts || []) watch.append(accountBlock(account));
  results.replaceChildren();
  const query = search.value.trim();
  if (!query) return;
  for (const account of found.accounts || []) {
    if ((follows.accounts || []).some((item) => item.username === account.username)) continue;
    results.append(accountBlock(account));
  }
}

function connectGsuite() {
  if (gsuiteStarting) return;
  if (gsuitePopup && !gsuitePopup.closed) {
    gsuitePopup.focus();
    return;
  }
  gsuiteStarting = true;
  note.textContent = "Opening Google…";
  fetch("/api/gmail")
    .then((res) => res.json())
    .then((status) => {
      if (!status.configured) {
        note.textContent =
          "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env, then restart. In Google Cloud, allow redirect URI http://127.0.0.1:8000/api/gmail/callback.";
        return;
      }
      gsuiteDone = false;
      gsuitePopup = window.open(
        "/api/gmail/start",
        "sheet-gsuite",
        "popup=yes,width=520,height=720"
      );
      if (!gsuitePopup) {
        note.textContent = "The Google window was blocked. Allow popups for this page, then try Connect Gmail again.";
        return;
      }
      note.textContent = "Choose your Google account and allow Sheet to read invite mail.";
      const timer = setInterval(() => {
        if (gsuitePopup && !gsuitePopup.closed) return;
        clearInterval(timer);
        if (!gsuiteDone) note.textContent = "Google sign-in was closed before access was granted.";
        refresh(false);
      }, 400);
    })
    .catch(() => {
      note.textContent = "Could not start Google sign-in.";
    })
    .finally(() => {
      gsuiteStarting = false;
    });
}

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin) return;
  if (!event.data || event.data.type !== "sheet-gmail") return;
  gsuiteDone = true;
  if (event.data.status === "denied") {
    note.textContent = "Google access was not granted.";
    return;
  }
  note.textContent = "Google access saved. Checking invites…";
  refresh(true);
});

search.addEventListener("input", () => refresh(false));
gmailLink.addEventListener("click", connectGsuite);
document.querySelector("#check").addEventListener("click", async () => {
  note.textContent = "Checking accounts on your list…";
  const checked = await fetch("/api/checks?force=true", { method: "POST" }).then((res) => res.json());
  note.textContent = (checked.accounts || []).map((item) => item.detail).join(" ");
  await refresh(false);
});
document.querySelector("#add-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  if (data.starts_at) data.starts_at = new Date(data.starts_at).toISOString();
  await fetch("/api/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  event.target.reset();
  await refresh(false);
});

const gmailResult = new URLSearchParams(location.search).get("gmail");
if (gmailResult && window.opener && window.opener !== window) {
  window.opener.postMessage({ type: "sheet-gmail", status: gmailResult }, location.origin);
  window.close();
} else {
  if (gmailResult) history.replaceState({}, "", "/");
  refresh(true);
}
