// Utilidades compartidas por las tres páginas. Todo se lee de archivos JSON
// estáticos generados por scripts/generate.py -- no hay backend ni llamadas
// a APIs externas desde el navegador.

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

async function fetchJSON(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`No se pudo cargar ${path} (${response.status})`);
  }
  return response.json();
}

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of children) {
    node.append(child);
  }
  return node;
}

// --- index.html ---

async function renderProjectList() {
  const list = document.getElementById("project-list");
  try {
    const projects = await fetchJSON("projects/index.json");
    list.replaceChildren();
    if (projects.length === 0) {
      list.append(el("li", { className: "muted", textContent: "Todavía no hay temas configurados." }));
      return;
    }
    for (const project of projects) {
      const link = el("a", {
        href: `topic.html?project=${encodeURIComponent(project.slug)}`,
        textContent: project.display_name,
      });
      list.append(el("li", { className: "card" }, [link]));
    }
  } catch (err) {
    list.replaceChildren(el("li", { className: "error", textContent: "No se pudieron cargar los temas." }));
    console.error(err);
  }
}

// --- topic.html ---

async function renderTopicPage() {
  const slug = getQueryParam("project");
  const title = document.getElementById("topic-title");
  const meta = document.getElementById("topic-meta");
  const list = document.getElementById("entry-list");

  if (!slug) {
    title.textContent = "Tema no encontrado";
    return;
  }

  try {
    const [config, dates] = await Promise.all([
      fetchJSON(`projects/${slug}/config.json`),
      fetchJSON(`projects/${slug}/index.json`),
    ]);

    title.textContent = config.display_name;
    meta.textContent = `Frecuencia: cada ${config.frequency_days} días`;

    list.replaceChildren();
    if (dates.length === 0) {
      list.append(el("li", { className: "muted", textContent: "Todavía no se ha generado ninguna entrega para este tema." }));
      return;
    }
    for (const date of dates) {
      const link = el("a", {
        href: `entry.html?project=${encodeURIComponent(slug)}&date=${encodeURIComponent(date)}`,
        textContent: date,
      });
      list.append(el("li", { className: "card" }, [link]));
    }
  } catch (err) {
    title.textContent = "Tema no encontrado";
    list.replaceChildren();
    console.error(err);
  }
}

// --- entry.html ---

async function renderEntryPage() {
  const slug = getQueryParam("project");
  const date = getQueryParam("date");
  const card = document.getElementById("paper-card");
  const backLink = document.getElementById("back-link");

  if (slug) {
    backLink.href = `topic.html?project=${encodeURIComponent(slug)}`;
  }

  if (!slug || !date) {
    card.replaceChildren(el("p", { className: "error", textContent: "Entrega no encontrada." }));
    return;
  }

  try {
    const entry = await fetchJSON(`projects/${slug}/entries/${date}.json`);
    renderPaper(card, entry.paper, date);
    renderQuiz(entry.quiz);
  } catch (err) {
    card.replaceChildren(el("p", { className: "error", textContent: "No se pudo cargar esta entrega." }));
    console.error(err);
  }
}

function renderPaper(card, paper, date) {
  const children = [
    el("p", { className: "muted", textContent: date }),
    el("h1", { textContent: paper.title }),
    el("p", { textContent: (paper.authors || []).join(", ") }),
    el("p", { className: "muted", textContent: [paper.journal, paper.year].filter(Boolean).join(" · ") }),
    el("p", { textContent: paper.abstract }),
  ];

  const links = el("p", {});
  if (paper.oa_url) {
    links.append(el("a", { href: paper.oa_url, textContent: "Leer el paper completo", target: "_blank", rel: "noopener" }));
    links.append(document.createTextNode(" · "));
  }
  links.append(el("a", { href: paper.openalex_url, textContent: "Ver en OpenAlex", target: "_blank", rel: "noopener" }));
  children.push(links);

  card.replaceChildren(...children);
}

function renderQuiz(questions) {
  const section = document.getElementById("quiz-section");
  const form = document.getElementById("quiz-form");
  const result = document.getElementById("quiz-result");

  section.hidden = false;
  form.replaceChildren();

  questions.forEach((q, questionIndex) => {
    const fieldset = el("fieldset", {}, [el("legend", { textContent: q.question })]);
    q.options.forEach((option, optionIndex) => {
      const inputId = `q${questionIndex}-o${optionIndex}`;
      const input = el("input", {
        type: "radio",
        name: `q${questionIndex}`,
        id: inputId,
        value: String(optionIndex),
      });
      const label = el("label", { htmlFor: inputId, textContent: option });
      fieldset.append(el("div", { className: "option" }, [input, label]));
    });
    form.append(fieldset);
  });

  document.getElementById("quiz-submit").onclick = () => {
    let correct = 0;
    questions.forEach((q, questionIndex) => {
      const chosen = form.querySelector(`input[name="q${questionIndex}"]:checked`);
      if (chosen && Number(chosen.value) === q.correct_index) {
        correct += 1;
      }
    });
    result.hidden = false;
    result.textContent = `${correct} de ${questions.length} correctas.`;
  };
}
