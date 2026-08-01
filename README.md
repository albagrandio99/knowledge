# knowledge

Mi primer proyecto con Git 🌱

Cada cierto tiempo (por defecto, cada semana), la app recomienda **sola**
un paper académico sobre un tema que me interesa, y genera un examen tipo
test para comprobar que lo he entendido. Sin listas manuales: el paper
sale de [OpenAlex](https://openalex.org) (base de datos académica abierta,
todas las disciplinas) y las preguntas las genera la API de OpenAI.

Los temas se organizan en **proyectos** independientes. De partida:

- `prehistoria` (incluye también género/arqueología de género)
- `geopolitica`

Cada uno con su propia frecuencia (semanal, quincenal...) y, si se quiere,
sus propios **papers de ejemplo**: en vez de (o además de) buscar por
palabras clave, se le pueden dar 1-2 papers que representen el tipo de
enfoque/perspectiva deseado, y la app buscará papers similares a esos
(usando los "related works" y los temas/conceptos que OpenAlex asigna a
cada paper). Así cada quien puede orientar su propio tema hacia el tipo
de información o de enfoque que le interesa.

Cualquiera puede clonar este repositorio, cambiar o añadir temas y tener
su propia versión.

## Cómo funciona

1. Cada día, un workflow de GitHub Actions (`.github/workflows/weekly-quiz.yml`)
   revisa cada proyecto y comprueba si le toca ya una entrega nueva, según
   su `frequency_days`.
2. Si le toca, `scripts/generate.py` busca un paper nuevo en OpenAlex sobre
   el tema, pide a OpenAI que genere el examen a partir del resumen, y
   guarda el resultado como un archivo JSON dentro del propio repositorio.
3. La web en `docs/` (publicada con GitHub Pages) simplemente lee esos
   JSON y los muestra — no hay servidor ni base de datos aparte, todo vive
   en el repositorio.

## Estructura

```
knowledge/
├── README.md
├── CLAUDE.md
├── .gitignore
├── .github/workflows/weekly-quiz.yml   # automatización (cron diario)
├── scripts/
│   ├── generate.py                     # busca el paper + genera el examen
│   └── requirements.txt
└── docs/                                # esto es lo que publica GitHub Pages
    ├── index.html / topic.html / entry.html
    ├── style.css / app.js
    └── projects/
        ├── index.json                   # lista de temas
        └── <tema>/
            ├── config.json              # búsqueda + frecuencia
            ├── used.json                # papers ya usados (no se repiten)
            ├── index.json               # fechas de entregas generadas
            └── entries/<fecha>.json     # paper + examen de esa entrega
```

## Añadir o ajustar un tema

Editar (o crear) `docs/projects/<tema>/config.json`:

```json
{
  "display_name": "Nombre a mostrar",
  "openalex_search": "términos de búsqueda en inglés",
  "example_papers": ["10.xxxx/doi-del-paper-1", "10.xxxx/doi-del-paper-2"],
  "frequency_days": 7,
  "last_generated": null
}
```

- `openalex_search`: términos de búsqueda de respaldo, se usan si no hay
  papers de ejemplo o si estos no dan suficientes candidatos.
- `example_papers`: DOIs (sin el `https://doi.org/` delante) de papers
  reales que representan el tipo de contenido que se quiere — de ahí sale
  la recomendación con prioridad. Vacío por defecto: hay que rellenarlo a
  mano con DOIs de papers que la propia persona conozca y le interesen (no
  se inventan ejemplos).

Y añadirlo a `docs/projects/index.json`. No hace falta tocar nada más —
el workflow lo recoge automáticamente en la siguiente ejecución.

## Puesta en marcha (una sola vez)

1. Crear una clave de API en [OpenAI](https://platform.openai.com) (con
   algo de crédito de facturación).
2. Crear una clave de API gratuita en
   [OpenAlex](https://openalex.org/settings/api).
3. En el repo de GitHub: **Settings → Secrets and variables → Actions** →
   añadir `OPENAI_API_KEY` y `OPENALEX_API_KEY`.
4. **Settings → Actions → General → Workflow permissions** → marcar "Read
   and write permissions".
5. **Settings → Pages → Source**: "Deploy from a branch" → rama `main`,
   carpeta `/docs`.
6. Lanzar el workflow una vez a mano desde la pestaña **Actions** ("Run
   workflow") para comprobar que todo funciona antes de esperar al primer
   disparo programado.

## Probarlo en local

```
cd docs && python3 -m http.server 8000
```

Y abrir `http://localhost:8000` — útil para ver cambios en la web antes
de subirlos.
