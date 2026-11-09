"use strict";
const $ = id => document.getElementById(id);
let token = "";
let currentPet = null;
const hash = new URLSearchParams(location.hash.slice(1));
if (hash.has("token")) {
  token = hash.get("token") || "";
  sessionStorage.setItem("hermie_token", token);
  history.replaceState(null, "", location.pathname);
} else {
  token = sessionStorage.getItem("hermie_token") || "";
}
const phrases = ["Nice to see you! ♡", "Let's make something!", "What a cozy day ✦", "I like it here!"];
function message(s){ $("message").textContent = s; }
function render(p){
  currentPet = p;
  $("pet-name").textContent = p.name;
  $("stage").textContent = p.stage.toUpperCase();
  $("level").textContent = "LVL " + String(p.level).padStart(2,"0");
  $("personality").textContent = p.personality + " little companion";
  $("xp").textContent = (p.xp % 50) + " / 50 XP";
  $("xp-bar").style.width = (p.xp % 50) * 2 + "%";
  for (const [id,key] of [["happy","happiness"],["energy","energy"],["bond","bond"]]) {
    $(id).style.width = p[key] + "%";
  }
  $("happy-num").textContent = p.happiness;
  $("energy-num").textContent = p.energy;
  $("bond-num").textContent = p.bond;
  $("snacks").textContent = p.snacks;
  $("tasks").textContent = p.tasks;
  $("bubble").textContent = p.energy < 20 ? "So sleepy... zzz" : phrases[Math.floor(p.xp / 20) % phrases.length];
  $("pet").classList.toggle("sleep",p.energy < 20);
}
async function request(action, name){
  const options = {headers:{"X-Hermie-Token":token}};
  if(action){
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify({action,name});
  }
  const response = await fetch(action ? "/api/action" : "/api/pet", options);
  const data = await response.json();
  if(!response.ok) throw new Error(data.error || "Request failed");
  render(data);
  return data;
}
function celebrate(){
  $("pet").classList.remove("celebrate");
  void $("pet").offsetWidth;
  $("pet").classList.add("celebrate");
  setTimeout(()=>$("pet").classList.remove("celebrate"),1600);
}
document.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click",async()=>{
  button.disabled = true;
  try{
    const action = button.dataset.action;
    await request(action);
    message(action === "feed" ? "Yum! Hermie loved that cookie." : action === "play" ? "That was fun! ✦" : "Time for a little rest.");
    if(action !== "rest") celebrate();
  }catch(e){message(e.message)}finally{button.disabled=false}
}));
$("rename-button").addEventListener("click",async()=>{
  try{await request("rename",$("rename").value);$("rename").value="";message("Your companion has a new name!")}catch(e){message(e.message)}
});
request().catch(e=>message("Unable to load pet: "+e.message+". Open the private link printed by the server."));
setInterval(()=>request().catch(()=>{}),15000);

function exportCard(){
  if(!currentPet){message("Pet is not loaded yet");return}
  const p=currentPet;
  const safe = s=>String(s).replace(/[&<>"']/g, ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&apos;"}[ch]));
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="500" viewBox="0 0 900 500"><rect width="900" height="500" rx="28" fill="#181325"/><rect x="22" y="22" width="856" height="456" rx="20" fill="#2a203e" stroke="#bd85b6" stroke-width="3"/><circle cx="235" cy="250" r="140" fill="#6e4c77"/><rect x="155" y="170" width="160" height="155" rx="35" fill="#ffbb7c" stroke="#d87f73" stroke-width="13"/><circle cx="205" cy="225" r="12" fill="#35243e"/><circle cx="264" cy="225" r="12" fill="#35243e"/><path d="M215 269 Q235 292 255 269" fill="none" stroke="#743b5c" stroke-width="8"/><text x="420" y="105" fill="#f9b881" font-family="monospace" font-size="24">HERMIE · COMPANION CARD</text><text x="420" y="195" fill="#fff0df" font-family="monospace" font-size="46">${safe(p.name)}</text><text x="420" y="247" fill="#e7b5fa" font-family="monospace" font-size="25">${safe(p.stage)} · LEVEL ${p.level}</text><text x="420" y="307" fill="#fff0df" font-family="monospace" font-size="24">${safe(p.personality)}</text><text x="420" y="362" fill="#d9c3d9" font-family="monospace" font-size="21">XP ${p.xp}   BOND ${p.bond}   SNACKS ${p.snacks}</text><text x="420" y="430" fill="#a99bb8" font-family="monospace" font-size="17">A LITTLE WORLD FOR HERMES AGENTS</text></svg>`;
  const blob = new Blob([svg],{type:"image/svg+xml"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");a.href=url;a.download="hermie-companion.svg";a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
  message("Your companion card is ready!");
}
$("export-card").addEventListener("click",exportCard);

const starField = $("star-field");
let starScore = 0;
let starTimer = null;
function stopStars(){
  if(starTimer !== null){clearInterval(starTimer);starTimer=null;}
  starField.replaceChildren();
  $("star-start").disabled = false;
}
$("star-start").addEventListener("click",()=>{
  stopStars();
  starScore=0;
  $("star-score").textContent="0 / 5";
  $("star-start").disabled=true;
  message("Catch the stars before they disappear!");
  let spawned=0;
  starTimer=setInterval(()=>{
    if(spawned++>=12){stopStars();message(starScore>=5?"Amazing! Hermie is dancing!":"Try again, you can do it!");return}
    const star=document.createElement("button");
    star.type="button";star.className="catch-star";star.textContent="✦";
    star.style.left=(8+Math.random()*78)+"%";
    star.style.top=(12+Math.random()*65)+"%";
    star.setAttribute("aria-label","Catch star");
    star.addEventListener("click",()=>{
      if(!star.isConnected)return;
      star.remove();starScore++;
      $("star-score").textContent=starScore+" / 5";
      if(starScore>=5){stopStars();celebrate();message("Five stars! Hermie is dancing! ✦")}
    });
    starField.append(star);
    setTimeout(()=>star.remove(),2200);
  },750);
});
$("plant").addEventListener("click",()=>{ $("bubble").textContent="I water this plant! 🌿";message("Hermie loves taking care of the little plant."); });
$("pet").addEventListener("click",()=>{celebrate();$("bubble").textContent="Boop! ♡";});
