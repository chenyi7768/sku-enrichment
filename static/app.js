(function () {
  const fileInput = document.getElementById("file-input");
  const fileName = document.getElementById("file-name");
  const btnRun = document.getElementById("btn-run");
  const btnSample = document.getElementById("btn-sample");
  const btnSampleHero = document.getElementById("btn-sample-hero");
  const statusEl = document.getElementById("status");
  const metaBox = document.getElementById("meta-box");
  const resultWrap = document.getElementById("result-wrap");
  const resultCount = document.getElementById("result-count");
  const btnDownload = document.getElementById("btn-download");
  const thead = document.querySelector("#result-table thead");
  const tbody = document.querySelector("#result-table tbody");

  let selectedFile = null;

  function setStatus(msg, type) {
    statusEl.hidden = !msg;
    statusEl.textContent = msg || "";
    statusEl.className = "status" + (type ? " " + type : "");
  }

  function renderTable(rows) {
    if (!rows || !rows.length) {
      resultWrap.hidden = true;
      return;
    }
    const cols = Object.keys(rows[0]);
    thead.innerHTML = "<tr>" + cols.map(c => "<th>" + escapeHtml(c) + "</th>").join("") + "</tr>";
    tbody.innerHTML = rows.map(r => {
      return "<tr>" + cols.map(c => {
        const v = r[c] == null ? "" : String(r[c]);
        const cls = (c === "SEO短描述" || c === "属性卖点" || c === "优化标题") ? " class=\"wrap-cell\"" : "";
        return "<td" + cls + " title=\"" + escapeAttr(v) + "\">" + escapeHtml(v) + "</td>";
      }).join("") + "</tr>";
    }).join("");
    resultWrap.hidden = false;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[ch]);
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/\n/g, " ");
  }

  function showResult(data) {
    const map = data.meta && data.meta.column_mapping ? data.meta.column_mapping : {};
    const mapStr = Object.keys(map).length
      ? Object.entries(map).map(([k, v]) => k + "→" + v).join("，")
      : "（自动推断）";
    metaBox.hidden = false;
    metaBox.innerHTML =
      "<strong>识别字段：</strong>" + escapeHtml(mapStr) +
      "<br/><strong>输入列：</strong>" + escapeHtml((data.meta.input_columns || []).join(", ")) +
      "<br/><strong>处理行数：</strong>" + data.total;
    resultCount.textContent = "（共 " + data.total + " 行，预览 " + data.preview_count + " 行）";
    btnDownload.href = "/api/download/" + data.token;
    renderTable(data.preview);
    setStatus("富化完成 ✓ 可预览并下载 CSV", "ok");
    resultWrap.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function runUpload(file) {
    setStatus("正在解析并富化…");
    btnRun.disabled = true;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch("/api/enrich", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText || "上传失败");
      showResult(data);
    } catch (e) {
      setStatus("失败：" + e.message, "error");
      resultWrap.hidden = true;
    } finally {
      btnRun.disabled = !selectedFile;
    }
  }

  async function runSample() {
    setStatus("正在加载建材样例并富化…");
    btnRun.disabled = true;
    try {
      const res = await fetch("/api/enrich-sample", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText || "样例失败");
      fileName.textContent = "已使用内置样例：building_supply_skus.xlsx";
      selectedFile = null;
      showResult(data);
    } catch (e) {
      setStatus("失败：" + e.message, "error");
    } finally {
      btnRun.disabled = !selectedFile;
    }
  }

  fileInput.addEventListener("change", () => {
    selectedFile = fileInput.files && fileInput.files[0];
    fileName.textContent = selectedFile ? selectedFile.name : "未选择文件";
    btnRun.disabled = !selectedFile;
    setStatus("");
  });

  btnRun.addEventListener("click", () => {
    if (selectedFile) runUpload(selectedFile);
  });
  btnSample.addEventListener("click", runSample);
  btnSampleHero.addEventListener("click", () => {
    document.getElementById("demo").scrollIntoView({ behavior: "smooth" });
    runSample();
  });
})();
