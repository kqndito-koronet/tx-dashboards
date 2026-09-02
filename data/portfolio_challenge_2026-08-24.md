# TX Portfolio Challenge — Aug 24, 2026

**Generado:** 2026-08-24
**Universo:** 124 Client Wholesalers + cross-reference con importers/growers
**Data:** sell/buy cubes through Jul 2026, fees through Jul 2026 (billed)
**5 sub-agents corrieron en paralelo:** SELL, BUY, HEALTH, LIST, POTENTIAL

---

## THE BIG NUMBERS

| Metric | Value | Context |
|---|---|---|
| Fees YTD | $1,478K | +34% YoY (target: +60%) → **gap de $380K vs target** |
| Online share | 18.1% | +0.5pp vs H2 2025 |
| Core+ Buy Digital | **3.2%** | vs K2K/eSuite 90%+ |
| Core+ missing eShop | **79%** (33/42) | Primary structural blocker |
| Billing gap (eSuite) | **$189K/yr** | 36 accounts with online sell, $0 fees configured |

---

## 1. SELL CARD — $189K en fees no configuradas + $522K si 10% offline se mueve

### Finding 1.1: BILLING GAP — 36 eSuite con online sell y $0 fees
**No es rate $0, no es K2K seller-side — es que billing no está configurado.**

Top 5 por online sell sin fees:

| Account | Online Sell YTD | Missing fees @1.5% |
|---|---|---|
| Palm Beach Whsle Flowers | $946K | $14.2K/yr |
| Jacksonville Flower Market | $898K | $13.5K/yr |
| R&W WHOLESALE | $891K | $13.4K/yr |
| M&M CUT FLORA | $746K | $11.2K/yr |
| HARDIN'S WHLSE - LIBERTY | $596K | $8.9K/yr |

**Total 36 eSuite:** $12.6M online sell → **$189K/yr en fees no capturadas**

ACTION: Verificar en SFDC si tienen fee rate configurado. Si no → billing activation con Payments team.

### Finding 1.2: OFFLINE OPPORTUNITY — 24 Core+ con <5% digital
Si 10% del offline se mueve online: **$522K incremental/yr**

Bill Doran domina: $207M sell, 2.7% digital. 10% shift = $302K en fees.

### Finding 1.3: Tier ≠ comportamiento digital
- has_eshop NO predice mayor digital% (6.1% con eShop vs 6.3% sin)
- El producto no es el blocker. La activación/training es el blocker.
- **Mayesh anomaly:** $197M, 23% digital, Core+, tiene Procurement pero NO eShop flag → VERIFICAR

---

## 2. BUY CARD — $523M al 3.2% digital, Procurement es la llave

### Finding 2.1: BUY sin SELL (5 accounts, $1.3M buy)
Compran 100% digital pero $0 sell. Ya confían en la plataforma.

| Account | Buy YTD | GMV | Tier | Lo que falta |
|---|---|---|---|---|
| DKAY Wholesale | $490K | $2.5M | Procurement | eShop |
| Full Pot Ft. Lauderdale | $372K | $8M | Procurement | eShop (Dormant!) |
| WB Floral Group | $118K | $2.5M | Procurement | Ya tiene eShop flag — activar |

ACTION: Warm sell de eShop — ya compraron el concepto por el buy side.

### Finding 2.2: SELL sin BUY (11 accounts, $19.3M sell)
Importadores vendiendo a escala pero comprando 100% offline.

| Account | Sell YTD | Lo que falta |
|---|---|---|
| Sunrite Farms | $6.3M | Procurement |
| Continental Flowers | $4.0M | Procurement |
| 9 más importers | $9.0M combinado | Procurement |

ACTION: "Ya confiás en nosotros para vender. Dejanos cerrar el loop en tu compra."

### Finding 2.3: Both-Modules es el único pattern que funciona
| Módulos | Buy Digital % |
|---|---|
| eShop + Procurement | **10.7%** |
| Procurement only | 1.7% |
| eShop only | **0.1%** (peor que nada!) |
| Ninguno | 1.7% |

**Kennicott proof case:** $35.9M buy, 24.6% digital, ambos módulos.

HIPÓTESIS H-B2: Procurement es la llave específica. eShop solo no cruza al buy side.

---

## 3. HEALTH CARD — 5 accounts en riesgo

### Finding 3.1: PMT sin impacto

| Account | PMT Lead | Diagnóstico |
|---|---|---|
| **Mellano Sales** ($35M) | Angie Ramirez | K2K connections aún en setup. No puede generar hasta que buyers se conecten. |
| **International Fresh** ($35K) | George Velez | 3 meses post go-live, **$297/mes**. Mauro: "el hábito se forma en semana 1 o nunca." |
| **WB Floral** ($2.5M) | Camila Peña | FALSO POSITIVO — es Retailer/Procurement. Métrica correcta = buy side ($92K KP activo). |

### Finding 3.2: Go-live muertos

| Account | Issue |
|---|---|
| **Fuji Wholesale** ($2M) | Recently live, $0 todo, **sin PMT lead**, zero Slack. Ghost account. |
| **Jose Miguel Cruz Gomez** | PMT "Completed" pero $0 sell + $0 buy. Paper go-live. |

### Finding 3.3: Declining
- **Galleria Farms** ($11.6M): fees -54%. EDI activo con duplicados en Armellini. $0 digital procurement. Posible issue técnico + gap buy-side.

### ACCIONES HEALTH
1. **Fuji:** Asignar PMT lead HOY + discovery call
2. **International Fresh:** Santiago Bermudez → digital habit reset call en 2 semanas
3. **Jose Miguel:** Fernando Yepez verifica K2K connections
4. **Mellano:** Angie confirma qué connections están pendientes
5. **Galleria:** Revisar EDI duplicates + iniciar conversación buy-side

---

## 4. LIST CARD — 79% de Core+ sin eShop, catalogs sin publicar

### Finding 4.1: 33 de 42 Core+ no tienen eShop
El sell surface principal no está activado. Es el blocker estructural.

Top sin eShop:
- Ninfa Flowers ($7.3M, 0% digital)
- JFS Wholesale ($7.1M, 0% digital)
- National Floral Supply ($6.5M, 0% digital)
- WE GOT FLOWERS ($5.2M, 0% digital)

### Finding 4.2: Catalogs cargados pero no publicados
9 Core+ con 200-4K SKUs en el sistema y **0 SKUs online**. Total $28M GMV.

Bill Doran: 23K SKUs cargados, solo 17% online. $116M GMV, eShop activo, 3.3% digital.

### Finding 4.3: Activation ≠ Usage
- 6 Core+ tienen eShop activo pero <5% digital (Bill Doran 3.3%, Flora Fresh 0.5%)
- El feature está encendido pero nadie lo usa
- Gap = training + behavior change, no product

---

## 5. POTENTIAL CARD — Tiers, GMV accuracy, oportunidades de pricing

### Finding 5.1: GMV updates needed (4 accounts)
| Account | Viejo | Nuevo | Razón |
|---|---|---|---|
| Continental Farms | $1.95M | $2.03M | Sell > estimate, Piso de red |
| Details Direct | $30K | $160K | Sell > estimate |
| Details Direct Core | $27K | $73K | Sell > estimate |
| Tutuli Flower Farms | $78K | $82K | Sell > estimate |

### Finding 5.2: ORA correcciones
- **Unifour:** ORA $3M → **$1M** (3 empleados, single location Hickory NC). Penetración real ~27%, no 9%.
- **Younger & Son:** ORA $4M → **mantener** (60K sqft, 60 años, 15 emp). Es un activation problem, no ORA inflado.

### Finding 5.3: Tier mismatches — oportunidad de pricing
**8 K2K con features de eSuite** (eShop + Procurement activos bajo contrato K2K):

| Account | GMV | Features usadas |
|---|---|---|
| Baisch & Skinner | $30M | eShop + Procurement |
| Southern Floral Co | $25M | eShop + Procurement |
| Cleveland Plant & Flower | $20M | eShop + Procurement |

ACTION: Revisar con Product/CS si están pagando eSuite pricing o K2K pricing. Si K2K → oportunidad de upgrade.

---

## CROSS-CARD PATTERNS

### Pattern 1: "Both Modules" es el único unlock
SELL + BUY + LIST: los únicos accounts con adopción digital significativa en AMBOS lados tienen eShop + Procurement juntos. Single-module no cruza.

### Pattern 2: $189K en fees no capturadas son quick win
36 eSuite con billing no configurado. No es negociación, no es activación — es configurar billing. El revenue existe, no lo estamos cobrando.

### Pattern 3: Importers son el buy-side sin tocar
$333M en buy GMV de importers Core+ al 1.4% digital. Venden por la plataforma pero compran 100% offline. Procurement es el lever.

### Pattern 4: Activation ≠ Usage
eShop activo pero no usado (Bill Doran 3.3%). PMT completado pero sin hábitos (International Fresh $297/mo). El gap no es producto — es behavior change.

### Pattern 5: Go-lives sin accountability
Fuji ($2M, sin PMT lead), Jose Miguel ($0, PMT "completed"). Accounts salen del pipeline sin verificación real de adopción.

---

## SIZING DEL GAP vs TARGET

| Fuente | Incremental anual | Dificultad |
|---|---|---|
| Billing gap (36 eSuite) | **$189K** | Baja — configurar billing |
| 10% offline shift (24 Core+) | **$522K** | Alta — behavior change |
| K2K tier upgrade (8 accounts) | **TBD** | Media — contract review |
| Importer Procurement activation | **TBD** | Media-alta — new module sale |
| Go-live accountability fixes | **Prevents churn** | Baja — process change |

**Fees target gap:** $1,478K actual × 12/7 = ~$2,534K projected vs $2,534K × 1.60 = $4,054K target. Gap = ~$1,520K. Los $189K de billing fix cubren 12% del gap. Los $522K de offline shift cubren 34%. Juntos = 47% del gap.
