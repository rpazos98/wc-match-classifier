# WC Match Classifier — Roadmap hacia el predictor Netflix

## Estado actual

Sistema de recomendación de partidos del Mundial 2026 que:
- Puntúa 104 partidos con 10 scorers independientes
- Aprende preferencias del usuario via pares A/B (logistic regression)
- Clasifica en 3 tiers: Imperdible / Vale la pena / Para resumen
- **Problema crítico:** aprendizaje no persiste entre sesiones

---

## Visión objetivo

Predictor híbrido estilo Netflix:
- Aprende del comportamiento real del usuario (vio / no vio / calificó)
- Mejora con cada interacción, sin pedir pares explícitos cada vez
- Con suficientes usuarios, aprovecha señal colaborativa ("usuarios como vos")
- Generaliza a partidos futuros sin configuración extra

---

## Arquitectura del sistema de recomendación

```
                    ┌─────────────────────┐
                    │   Preference Store   │
                    │ (user, match, chose) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
    ┌─────────▼──────────┐          ┌──────────▼──────────┐
    │  Content-Based     │          │  Collaborative       │
    │  Logistic Reg.     │          │  (user similarity)   │
    │  per-user weights  │          │  k-NN en embeddings  │
    └─────────┬──────────┘          └──────────┬──────────┘
              │                                 │
              └────────────┬────────────────────┘
                           │
                   ┌───────▼───────┐
                   │  Blend score  │
                   │  α*CB + β*CF  │
                   └───────────────┘
```

- **CB (Content-Based):** funciona desde usuario #1. Pesos por logistic regression sobre features del partido.
- **CF (Collaborative):** mejora conforme llegan más usuarios. k-NN sobre user embeddings.
- `α, β` dinámicos: arranca α=1, β=0 → se mueve según confianza (n_interactions del usuario).

---

## Fases de implementación

### Fase 1 — Persistence Layer (próximo paso)

**Objetivo:** guardar cada observación de preferencia como dato de entrenamiento.

**Schema nuevo en SQLite:**

```sql
CREATE TABLE users (
  user_id     TEXT PRIMARY KEY,
  profile_json TEXT NOT NULL,          -- UserProfile serializado
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE preference_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     TEXT NOT NULL REFERENCES users(user_id),
  match_a_id  INTEGER,                 -- NULL si source=watched/skipped/rated
  match_b_id  INTEGER,
  chosen      TEXT CHECK(chosen IN ('a','b','skip')),
  features_a  TEXT,                    -- JSON: {scorer: raw_score, ...}
  features_b  TEXT,
  source      TEXT CHECK(source IN ('pair','watched','skipped','rated')),
  rating      REAL,                    -- 1–5 si source=rated, NULL si no
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_weights (
  user_id     TEXT NOT NULL REFERENCES users(user_id),
  scorer_name TEXT NOT NULL,
  weight      REAL NOT NULL,
  n_events    INTEGER DEFAULT 0,       -- cuántas obs usó para este fit
  updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, scorer_name)
);
```

**Cambios en web.py:**
- `POST /api/user` — crear/actualizar usuario con perfil
- `GET /api/user/{id}/weights` — retorna pesos actuales (DB → fallback default)
- `POST /api/learn/fit` — guarda eventos + refit + persiste pesos
- `POST /api/match/{id}/watched` — registra partido visto (señal implícita)
- `POST /api/match/{id}/skipped` — registra partido salteado
- `POST /api/match/{id}/rate` — rating 1–5 post-partido

**Cambios en learning.py:**
- `fit_from_events(events: List[PreferenceEvent]) -> Dict[str, float]`
- Incremental: re-fitea sobre todos los eventos del usuario, no solo los nuevos

---

### Fase 2 — Feedback implícito

Registrar comportamiento real sin preguntar al usuario:
- Marcó partido como favorito → positivo
- Buscó el partido en el listado → señal débil positiva
- Cambió clasificación manualmente → señal fuerte

Cada acción dispara un micro-refit (o encola para batch refit).

---

### Fase 3 — Collaborative Filtering

**Cuando:** ≥ 50 usuarios con ≥ 20 eventos cada uno (≈ 1000 observaciones).

**Approach:** Matrix Factorization sobre (user × scorer_weights):
- Cada usuario = vector de 10 dimensiones (sus pesos aprendidos)
- k-NN en ese espacio → "usuarios similares"
- CF score = promedio ponderado de qué vieron usuarios similares

**Blend dinámico:**
```python
α = min(1.0, n_user_events / 30)   # confianza en CB crece con eventos propios
β = min(0.4, n_total_users / 200)  # confianza en CF crece con masa de usuarios
score = normalize(α * cb_score + β * cf_score)
```

---

### Fase 4 — Two-Tower (largo plazo)

Si el sistema escala más allá del Mundial 2026 a otras competiciones:
- User Tower: embedding de perfil + historial
- Match Tower: embedding de features del partido
- Dot product → probabilidad de ver

Pre-training con datos históricos 2018/2022.

---

## Dataset de entrenamiento

Cada `preference_event` = una fila de entrenamiento:

| Campo | Rol |
|-------|-----|
| `features_a/b` | Features (10 scorer values) |
| `chosen` | Label binario |
| `rating` | Label continuo (1–5) |
| `source` | Peso de la señal (pair > rated > watched > skipped) |

Con 50 usuarios × 30 pares = 1500 filas → suficiente para CF.

---

## Qué NO cambia

- Los 10 scorers y su lógica interna
- La clasificación en 3 tiers
- El sistema de simulación Monte Carlo
- Los embeddings de jugadores
- El schema actual de partidos/equipos/jugadores

---

## Criterio de éxito

| Métrica | Target |
|---------|--------|
| Retención de pesos entre sesiones | 100% (Fase 1) |
| Reducción de pares necesarios para warm-up | < 5 (vs. 12 actual) |
| Precisión predicción "Imperdible" vs. visto real | > 70% |
| Tiempo de refit incremental | < 200ms |
