# Métricas de analítica

La API expone métricas base y ratios derivados. Las métricas base se guardan en
`ad_insights` (una fila por anuncio y día); los ratios se calculan al consultar.

## Fórmulas

| Indicador | Fórmula | Campo de la API |
|---|---|---|
| Frequency | impressions / reach | `frequency` |
| CTR | clicks / impressions × 100 | `ctr` |
| CPC | spend / clicks | `cpc` |
| CPM | spend / impressions × 1000 | `cpm` |
| CPL | spend / leads | `cpl` |
| Conversion Rate | leads / landing_page_views × 100 | `conversion_rate` |
| ROAS | revenue / spend | `roas` |

ROI no se expone en el MVP: requiere beneficio y costos reales, no solo ingresos
atribuidos. Mostrar un ROI calculado solo con `revenue` sería engañoso.

## Reglas de cálculo

1. Primero se suman las métricas base del periodo y **después** se calculan los
   ratios. Nunca se promedian ratios diarios: el CTR del periodo no es el promedio
   de los CTR diarios.
2. Si el denominador es cero, el ratio es `null`. No se divide por cero ni se
   devuelve `0` como sustituto.
3. `reach` es el número de personas únicas. No es sumable entre días ni entre
   anuncios. Por eso:
   - `overview`, `campaigns` y `trends` devuelven `reach` y `frequency` como `null`.
   - `ads` devuelve `reach` y `frequency` solo cuando el rango es de un único día;
     con varios días devuelve `null`.
4. `landing_page_views` son las visitas atribuidas por la plataforma publicitaria
   (Meta), no eventos medidos en nuestra propia landing. Una integración futura
   deberá distinguir ambas fuentes.
5. Los ratios se redondean a seis decimales y se serializan como números. Los
   importes (`spend`, `revenue`) se mantienen como `Decimal`/`NUMERIC`, se
   normalizan a dos decimales y se serializan como cadena para no perder precisión.

## Agregaciones de la API

| Endpoint | Agrupación | `reach`/`frequency` |
|---|---|---|
| `GET /api/v1/analytics/overview` | Toda la organización | `null` |
| `GET /api/v1/analytics/campaigns` | Campaña | `null` |
| `GET /api/v1/analytics/ads` | Anuncio | Solo con rango de un día |
| `GET /api/v1/analytics/trends` | Día, semana o mes | `null` |

- El rango `date_from`/`date_to` es inclusivo y obligatorio.
- Las campañas y anuncios archivados se incluyen si tienen métricas: el archivado es
  operativo y no borra el histórico.
- Las entidades sin filas en `ad_insights` no aparecen en los listados por campaña o
  anuncio. `overview` devuelve ceros y ratios `null` si el rango no tiene datos.
- Todos los endpoints filtran por la organización autenticada.
- `trends` acepta `granularity=day|week|month`; los periodos se recortan al rango
  solicitado para que las etiquetas no sugieran datos fuera de la consulta.

## Ejemplo

Dos anuncios, dos días:

| Día | Impresiones | Clics | Gasto | Leads | Visitas | Ingresos |
|---|---|---|---|---|---|---|
| 2026-10-01 | 1500 | 75 | 150.00 | 15 | 60 | 500.00 |
| 2026-10-02 | 300 | 55 | 30.00 | 3 | 30 | 0.00 |
| Total | 1800 | 130 | 180.00 | 18 | 90 | 500.00 |

- CTR total = 130 / 1800 × 100 = **7.222222 %**.
- Promedio incorrecto de CTR diarios = (5 % + 18.333333 %) / 2 = 11.666667 %.
- CPC = 180 / 130 = **1.384615**.
- CPM = 180 / 1800 × 1000 = **100**.
- CPL = 180 / 18 = **10**.
- Conversion Rate = 18 / 90 × 100 = **20 %**.
- ROAS = 500 / 180 = **2.777778**.
