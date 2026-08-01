# knowledge

Repositorio personal de Alba. Es su primer proyecto de programación/Git
("proyecto 0") — explica los conceptos técnicos y las acciones de Git en
términos simples antes de asumir que los conoce.

## Qué es este proyecto

Una app de aprendizaje: periódicamente (por defecto cada semana, ajustable
por tema) recomienda automáticamente un paper académico sobre un tema de
interés, y genera un examen tipo test sobre él. Ni el paper ni las
preguntas se curan a mano: el paper sale de la API de OpenAlex y el examen
lo genera la API de OpenAI a partir del resumen.

Proyectos base: `prehistoria` (incluye género/arqueología de género) y
`geopolitica`. Cada proyecto tiene su propia frecuencia y, opcionalmente,
sus propios "papers de ejemplo" (`docs/projects/<tema>/config.json`) que
orientan el tipo de contenido/perspectiva que se recomienda — ver más
abajo.

Objetivo: que otras personas puedan acceder a este repositorio y usar la
misma app con sus propios temas.

## Arquitectura (ya construida, ver el plan en
`~/.claude/plans/sequential-munching-canyon.md` para el razonamiento completo)

- **Frontend**: web estática en `docs/` (publicada con GitHub Pages,
  fuente = rama `main`, carpeta `/docs` — ese modo simple de Pages solo
  admite `/` o `/docs`, ningún otro nombre de carpeta).
- **Generación de contenido**: `scripts/generate.py`, ejecutado por
  `.github/workflows/weekly-quiz.yml` (cron diario + `workflow_dispatch`
  manual). Selección del candidato, en orden: (1) si `example_papers`
  tiene DOIs, usa los `related_works` de esos papers en OpenAlex y sus
  `concepts` como filtro; (2) si eso no da suficientes candidatos, busca
  por `concepts.id` de esos ejemplos; (3) si sigue sin haber suficientes
  (o no hay `example_papers`), cae en `openalex_search` por palabras
  clave. Reconstruye el abstract (`abstract_inverted_index` → texto),
  llama a OpenAI para el examen, y escribe el resultado como JSON dentro
  de `docs/projects/<tema>/entries/`. El propio job hace commit y push
  del resultado (`permissions: contents: write` en el workflow basta, no
  hace falta token aparte).
- **Acceso abierto**: la app solo tiene sentido si el paper se puede leer
  de verdad, así que `find_candidate_paper` descarta cualquier candidato
  sin copia legal en abierto en vez de recomendarlo igualmente.
  `candidates_from_concepts`/`candidates_from_keywords` ya piden
  `open_access.is_oa:true` a OpenAlex; los `related_works` de
  `example_papers` no vienen filtrados por la API, así que ahí se
  comprueba caso por caso (`oa_url` de OpenAlex o, si falta, Unpaywall vía
  `find_open_access_url`) y se pasa al siguiente candidato si de verdad
  está cerrado. Unpaywall no requiere clave, solo un email de contacto
  (`UNPAYWALL_EMAIL`, ver workflow) — no hace falta que sea personal.
- **`example_papers`**: nunca rellenar con DOIs inventados — deben ser
  papers reales que la persona dueña del tema conoce y quiere usar como
  referencia de enfoque. Si no los tiene todavía, dejar la lista vacía
  (cae automáticamente al buscador por palabras clave).
- **"Base de datos"**: no hay ninguna de verdad — los JSON dentro del
  repo son el almacenamiento. `used.json` evita repetir papers;
  `last_generated` en `config.json` controla la frecuencia por tema.
- **Secretos**: `OPENAI_API_KEY` y `OPENALEX_API_KEY` viven como secrets
  de GitHub Actions, nunca en el código ni en el JS del navegador (que
  solo lee los JSON ya generados).

## Convenciones

- Nada de sobre-ingeniería: es un proyecto de aprendizaje personal, no un
  producto — preferir la solución más simple que funcione.
- Cualquier paper que aparezca debe llevar su referencia verificable
  (autor, año, revista/DOI o enlace) — ya garantizado por venir de
  OpenAlex, no añadir fuentes que no lo cumplan.
- Los nombres de modelo de OpenAI cambian con el tiempo — si
  `scripts/generate.py` empieza a fallar en la llamada a OpenAI, comprobar
  primero si `OPENAI_MODEL` sigue vigente en la documentación de OpenAI.
