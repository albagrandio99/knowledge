"""Genera, para cada proyecto en docs/projects/ cuya frecuencia toque hoy,
un paper recomendado (via OpenAlex) y un examen tipo test sobre él (via
OpenAI), y los escribe como JSON estático dentro del propio repositorio.

Pensado para ejecutarse desde la raíz del repo (así lo hace el workflow de
GitHub Actions en .github/workflows/weekly-quiz.yml), con OPENAI_API_KEY y
OPENALEX_API_KEY como variables de entorno.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path

import requests
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = REPO_ROOT / "docs" / "projects"

# Modelo barato y suficiente para generar unas pocas preguntas de tipo test
# a partir de un resumen corto. Los nombres de modelo de OpenAI cambian con
# el tiempo -- si esto empieza a fallar, comprobar el nombre vigente en
# platform.openai.com/docs/models.
OPENAI_MODEL = "gpt-4o-mini"

OPENALEX_API_KEY = os.environ["OPENALEX_API_KEY"]
UNPAYWALL_EMAIL = os.environ["UNPAYWALL_EMAIL"]
# Al lanzarlo a mano desde la pestaña Actions ("Run workflow") se ignora
# frequency_days y se genera igualmente, para poder probar sin esperar días.
FORCE_GENERATE = os.environ.get("FORCE_GENERATE", "false").lower() == "true"
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def reconstruct_abstract(inverted_index):
    """OpenAlex no da el abstract como texto plano, sino como un diccionario
    palabra -> lista de posiciones (por temas de licencia de republicación).
    Hay que reordenar las palabras según su posición para recuperar el texto.
    """
    if not inverted_index:
        return None
    max_pos = max(p for positions in inverted_index.values() for p in positions)
    words = [""] * (max_pos + 1)
    for word, positions in inverted_index.items():
        for p in positions:
            words[p] = word
    return " ".join(words)


def openalex_get(path, **params):
    params["api_key"] = OPENALEX_API_KEY
    response = requests.get(f"https://api.openalex.org{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def short_id(openalex_id):
    return openalex_id.rsplit("/", 1)[-1]


def candidates_from_examples(example_dois):
    """Los 'papers de ejemplo' definen el tipo de contenido que se quiere:
    en vez de depender solo de palabras clave, se buscan papers similares
    (related_works, que OpenAlex ya calcula) a esos ejemplos, y se recogen
    sus 'concepts' (temas) para usarlos como filtro de respaldo.
    """
    candidates = []
    concept_ids = set()
    for doi in example_dois:
        try:
            example_work = openalex_get(f"/works/https://doi.org/{doi}")
        except requests.HTTPError:
            continue
        for concept in (example_work.get("concepts") or [])[:3]:
            concept_ids.add(short_id(concept["id"]))
        for related_id in (example_work.get("related_works") or [])[:10]:
            try:
                candidates.append(openalex_get(f"/works/{short_id(related_id)}"))
            except requests.HTTPError:
                continue
    return candidates, concept_ids


def candidates_from_concepts(concept_ids):
    if not concept_ids:
        return []
    result = openalex_get(
        "/works",
        filter=f"concepts.id:{'|'.join(concept_ids)},has_abstract:true,open_access.is_oa:true",
        sort="cited_by_count:desc",
        per_page=25,
    )
    return result["results"]


def candidates_from_keywords(search_terms):
    if not search_terms:
        return []
    result = openalex_get(
        "/works",
        search=search_terms,
        filter="has_abstract:true,open_access.is_oa:true",
        sort="relevance_score:desc",
        per_page=25,
    )
    return result["results"]


def find_candidate_paper(config, used_ids):
    example_dois = config.get("example_papers") or []
    pool = []
    concept_ids = set()

    if example_dois:
        related, concept_ids = candidates_from_examples(example_dois)
        pool.extend(related)
    if len(pool) < 10:
        pool.extend(candidates_from_concepts(concept_ids))
    if len(pool) < 10:
        pool.extend(candidates_from_keywords(config.get("openalex_search")))

    seen = set()
    for work in pool:
        work_id = short_id(work["id"])
        if work_id in used_ids or work_id in seen:
            continue
        seen.add(work_id)
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
        if not abstract:
            continue
        # Un paper que no se puede leer gratis no sirve para esta app, aunque
        # encaje en tema: candidates_from_concepts/keywords ya piden solo
        # open_access.is_oa:true, pero los related_works de example_papers no
        # vienen filtrados, así que aquí se comprueba (con Unpaywall de
        # respaldo) y se descarta el candidato si de verdad está cerrado.
        oa_url = (work.get("open_access") or {}).get("oa_url") or find_open_access_url(work.get("doi"))
        if not oa_url:
            continue
        return work, abstract, oa_url

    return None, None, None


def generate_quiz(title, abstract):
    prompt = (
        "Basándote únicamente en este título y resumen de un paper académico, "
        "genera entre 3 y 5 preguntas tipo test para comprobar que alguien lo "
        "ha leído y entendido. Cada pregunta debe tener 4 opciones y una sola "
        "correcta.\n\n"
        f"Título: {title}\n\nResumen: {abstract}\n\n"
        'Responde SOLO con JSON con esta forma exacta: '
        '{"questions": [{"question": "...", "options": ["...", "...", "...", "..."], '
        '"correct_index": 0}]}'
    )

    completion = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(completion.choices[0].message.content)["questions"]


def find_open_access_url(doi):
    """OpenAlex a veces marca un paper como cerrado aunque exista una copia
    legal en abierto (preprint del autor, repositorio institucional...).
    Unpaywall es gratis y no requiere clave, solo un email de contacto.
    """
    if not doi:
        return None
    bare_doi = doi.removeprefix("https://doi.org/")
    try:
        response = requests.get(
            f"https://api.unpaywall.org/v2/{bare_doi}",
            params={"email": UNPAYWALL_EMAIL},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None
    best_location = response.json().get("best_oa_location")
    return best_location["url"] if best_location else None


def get_journal_name(work):
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    return source.get("display_name")


def is_due(config):
    if FORCE_GENERATE or not config.get("last_generated"):
        return True
    last = date.fromisoformat(config["last_generated"])
    return (date.today() - last).days >= config["frequency_days"]


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def process_project(project_dir):
    slug = project_dir.name
    config_path = project_dir / "config.json"
    config = load_json(config_path, None)
    if config is None:
        return

    if not is_due(config):
        print(f"[{slug}] no toca todavía, se salta.")
        return

    used_path = project_dir / "used.json"
    used_ids = load_json(used_path, [])

    work, abstract, oa_url = find_candidate_paper(config, used_ids)
    if work is None:
        print(f"[{slug}] no se encontró ningún paper nuevo en abierto, se salta esta vez.")
        return

    questions = generate_quiz(work["title"], abstract)
    doi = work.get("doi")

    today = date.today().isoformat()
    entry = {
        "project": slug,
        "date_generated": today,
        "paper": {
            "openalex_id": work["id"].rsplit("/", 1)[-1],
            "doi": doi,
            "title": work["title"],
            "authors": [
                a["author"]["display_name"] for a in work.get("authorships", [])
            ],
            "year": work.get("publication_year"),
            "journal": get_journal_name(work),
            "citation_count": work.get("cited_by_count"),
            "openalex_url": work["id"],
            "oa_url": oa_url,
            "abstract": abstract,
        },
        "quiz": questions,
    }

    entries_dir = project_dir / "entries"
    entries_dir.mkdir(exist_ok=True)
    write_json(entries_dir / f"{today}.json", entry)

    used_ids.append(entry["paper"]["openalex_id"])
    write_json(used_path, used_ids)

    entries_index_path = project_dir / "index.json"
    entries_index = load_json(entries_index_path, [])
    entries_index = [d for d in entries_index if d != today]
    entries_index.insert(0, today)
    write_json(entries_index_path, entries_index)

    config["last_generated"] = today
    write_json(config_path, config)

    print(f"[{slug}] entrega generada para {today}: {work['title']}")


def main():
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        try:
            process_project(project_dir)
        except Exception as exc:
            print(f"[{project_dir.name}] ERROR, se salta este tema: {exc}")


if __name__ == "__main__":
    main()
