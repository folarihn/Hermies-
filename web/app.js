"use strict";
const $ = id => document.getElementById(id);
let token = "";
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
