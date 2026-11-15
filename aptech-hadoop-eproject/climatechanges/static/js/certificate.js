/* Certificate of Completion, drawn on canvas, downloadable as PNG */
(function(){
  "use strict";
  var canvas = document.getElementById("cert-canvas");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var nameInput = document.getElementById("cert-name");
  var downloadBtn = document.getElementById("cert-download");

  var W = 1000, H = 700;
  canvas.width = W; canvas.height = H;

  function todayStr(){
    var d = new Date();
    var months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
    return months[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear();
  }

  function draw(name){
    name = (name || "").trim() || "Your Name Here";

    // soft paper gradient wash instead of flat white
    var bg = ctx.createLinearGradient(0, 0, W, H);
    bg.addColorStop(0, "#FFFFFF");
    bg.addColorStop(1, "#F6F4EE");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    // faint radial glow behind the seal, premium-paper feel
    var glow = ctx.createRadialGradient(W / 2, 90, 10, W / 2, 90, 260);
    glow.addColorStop(0, "rgba(22,132,122,0.10)");
    glow.addColorStop(1, "rgba(22,132,122,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, W, H);

    // outer border, gradient teal->amber for a richer frame
    var borderGrad = ctx.createLinearGradient(0, 0, W, H);
    borderGrad.addColorStop(0, "#0B5560");
    borderGrad.addColorStop(1, "#0A4641");
    ctx.strokeStyle = borderGrad;
    ctx.lineWidth = 10;
    ctx.strokeRect(20, 20, W - 40, H - 40);
    ctx.strokeStyle = "#EE8C3C";
    ctx.lineWidth = 3;
    ctx.strokeRect(38, 38, W - 76, H - 76);
    ctx.strokeStyle = "rgba(217,105,26,0.35)";
    ctx.lineWidth = 1;
    ctx.strokeRect(46, 46, W - 92, H - 92);

    // corner isoline-style flourish (simple arcs, echoes site motif)
    ctx.strokeStyle = "rgba(14,92,86,0.25)";
    ctx.lineWidth = 2;
    for (var i = 0; i < 4; i++){
      ctx.beginPath();
      ctx.arc(70, 70, 26 + i * 10, Math.PI, 1.5 * Math.PI);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(W - 70, H - 70, 26 + i * 10, 0, 0.5 * Math.PI);
      ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(W - 70, 70, 26, 1.5 * Math.PI, 2 * Math.PI); ctx.stroke();
    ctx.beginPath(); ctx.arc(70, H - 70, 26, 0.5 * Math.PI, Math.PI); ctx.stroke();

    // gold medallion seal, top-center — a premium touch, sits above the eyebrow
    var seal = ctx.createLinearGradient(W / 2 - 22, 40, W / 2 + 22, 84);
    seal.addColorStop(0, "#F5B87D");
    seal.addColorStop(0.5, "#D9691A");
    seal.addColorStop(1, "#EE8C3C");
    ctx.save();
    ctx.beginPath();
    ctx.arc(W / 2, 62, 22, 0, Math.PI * 2);
    ctx.fillStyle = seal;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#FFFFFF";
    ctx.stroke();
    ctx.fillStyle = "#FFFFFF";
    ctx.font = "700 18px 'Fraunces', Georgia, serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("GW", W / 2, 63);
    ctx.textBaseline = "alphabetic";
    ctx.restore();

    ctx.textAlign = "center";

    ctx.fillStyle = "#D9691A";
    ctx.font = "700 16px 'JetBrains Mono', monospace";
    ctx.fillText("GLOBAL WARMING EXPLORER · GUIDED COURSE", W / 2, 118);

    ctx.fillStyle = "#11201C";
    ctx.font = "700 46px 'Fraunces', Georgia, serif";
    ctx.fillText("Certificate of Completion", W / 2, 170);

    ctx.fillStyle = "#45564E";
    ctx.font = "400 18px 'Inter', sans-serif";
    ctx.fillText("This certifies that", W / 2, 250);

    ctx.fillStyle = "#0A4641";
    ctx.font = "700 44px 'Fraunces', Georgia, serif";
    // shrink font if the name is long
    var fontSize = 44;
    ctx.font = fontSize + "px 'Fraunces', Georgia, serif";
    while (ctx.measureText(name).width > W - 200 && fontSize > 22){
      fontSize -= 2;
      ctx.font = "700 " + fontSize + "px 'Fraunces', Georgia, serif";
    }
    ctx.fillText(name, W / 2, 320);

    ctx.strokeStyle = "#CBD8CD";
    ctx.beginPath();
    ctx.moveTo(W / 2 - 220, 340);
    ctx.lineTo(W / 2 + 220, 340);
    ctx.stroke();

    ctx.fillStyle = "#45564E";
    ctx.font = "400 18px 'Inter', sans-serif";
    wrapText("has successfully completed all eight lessons of the Global Warming Explorer guided course, covering the science, effects, and real actions behind a warming world.", W / 2, 380, 620, 26);

    ctx.fillStyle = "#6E7D75";
    ctx.font = "400 15px 'JetBrains Mono', monospace";
    ctx.fillText(todayStr(), W / 2, 480);

    // signature block
    ctx.strokeStyle = "#CBD8CD";
    ctx.beginPath();
    ctx.moveTo(W / 2 - 160, 560);
    ctx.lineTo(W / 2 + 160, 560);
    ctx.stroke();
    ctx.fillStyle = "#11201C";
    ctx.font = "700 17px 'Fraunces', Georgia, serif";
    ctx.fillText("Babatunde Ayoola Awoyemi", W / 2, 585);
    ctx.fillStyle = "#6E7D75";
    ctx.font = "400 14px 'Inter', sans-serif";
    ctx.fillText("Techbase Consultant Services · Global Warming Explorer", W / 2, 606);

    ctx.textAlign = "left";
  }

  function wrapText(text, cx, y, maxWidth, lineHeight){
    var words = text.split(" ");
    var line = "";
    var lines = [];
    for (var i = 0; i < words.length; i++){
      var test = line + words[i] + " ";
      if (ctx.measureText(test).width > maxWidth && line){
        lines.push(line);
        line = words[i] + " ";
      } else {
        line = test;
      }
    }
    lines.push(line);
    lines.forEach(function(l, idx){
      ctx.fillText(l.trim(), cx, y + idx * lineHeight);
    });
  }

  function safeDraw(){
    try{
      if (document.fonts && document.fonts.ready){
        document.fonts.ready.then(function(){ draw(nameInput ? nameInput.value : ""); });
      }
      draw(nameInput ? nameInput.value : "");
    }catch(e){ draw(nameInput ? nameInput.value : ""); }
  }

  if (nameInput) nameInput.addEventListener("input", safeDraw);
  safeDraw();

  if (downloadBtn){
    downloadBtn.addEventListener("click", function(){
      var name = (nameInput ? nameInput.value.trim() : "") || "certificate";
      var link = document.createElement("a");
      link.download = "global-warming-explorer-certificate-" + name.replace(/\s+/g, "-").toLowerCase() + ".png";
      link.href = canvas.toDataURL("image/png");
      link.click();
      if (window.GWConfetti) window.GWConfetti({ count: 150, duration: 3000 });
    });
  }

  /* ---- share the achievement ---- */
  var shareStatus = document.getElementById("cert-share-status");
  var shareNativeBtn = document.getElementById("cert-share-native");
  var shareWhatsappBtn = document.getElementById("cert-share-whatsapp");
  var copyLinkBtn = document.getElementById("cert-copy-link");
  var CERT_URL = "https://babatundeawo.github.io/globalwarming/certificate.html";

  function shareText(){
    var name = (nameInput ? nameInput.value.trim() : "");
    var who = name ? name + " just" : "I just";
    return who + " completed the Global Warming Explorer course! 🌍 Free 8-lesson climate course, try it: " + CERT_URL;
  }

  function setStatus(msg){
    if (shareStatus) shareStatus.textContent = msg;
  }

  function canvasToBlob(){
    return new Promise(function(resolve){
      canvas.toBlob(function(blob){ resolve(blob); }, "image/png");
    });
  }

  // Native share (mobile browsers): shares the actual certificate image where supported.
  if (shareNativeBtn){
    if (navigator.share){
      shareNativeBtn.hidden = false;
      shareNativeBtn.addEventListener("click", function(){
        canvasToBlob().then(function(blob){
          var name = (nameInput ? nameInput.value.trim() : "") || "certificate";
          var fileName = "global-warming-explorer-certificate-" + name.replace(/\s+/g, "-").toLowerCase() + ".png";
          var file = blob ? new File([blob], fileName, {type: "image/png"}) : null;
          var shareData = { title: "Global Warming Explorer — Certificate", text: shareText(), url: CERT_URL };
          if (file && navigator.canShare && navigator.canShare({files: [file]})){
            shareData.files = [file];
          }
          navigator.share(shareData).catch(function(){ /* user cancelled, ignore */ });
        });
      });
    }
  }

  // WhatsApp: always available, no permissions needed, opens wa.me with prefilled text.
  if (shareWhatsappBtn){
    shareWhatsappBtn.addEventListener("click", function(e){
      e.preventDefault();
      var url = "https://wa.me/?text=" + encodeURIComponent(shareText());
      window.open(url, "_blank", "noopener");
    });
  }

  // Copy link: works everywhere, including desktop with no share sheet.
  if (copyLinkBtn){
    copyLinkBtn.addEventListener("click", function(){
      var done = function(){ setStatus("Link copied ✓"); setTimeout(function(){ setStatus(""); }, 2500); };
      var fail = function(){
        window.prompt("Copy this link:", CERT_URL);
      };
      if (navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(CERT_URL).then(done, fail);
      } else {
        fail();
      }
    });
  }
})();
