# Metodología: cómo leer los números

## Qué mide y qué no mide

- **Mide** el tono de lo que se publica en Bluesky en castellano sobre cada tema, y cómo cambia en el tiempo.
- **No mide** la opinión de la población argentina. Bluesky tiene menos usuarios argentinos que
  X y no es una muestra representativa: es un complemento, no una encuesta.
- **No mide intención de voto.** Por la Ley 26.215, el proyecto no publica nada que pueda leerse
  como una encuesta electoral.
- **No perfila personas.** Solo se reportan agregados por tema; no se guardan autores.

## Sesgos conocidos

| Sesgo | Efecto | Qué se hace |
|---|---|---|
| **Muestreo**: quién usa Bluesky | Sobrerrepresenta a ciertos perfiles (más urbanos y politizados) | Aviso en el tablero; se comparan tendencias, no niveles absolutos |
| **Idioma**: `lang=es` incluye España, México, etc. | Términos genéricos traen posts de otros países | Se usan términos argentinos (subte, ANSES, Edesur…); se evitan genéricos como "colectivos" |
| **Actividad de la plataforma** | En 2026 hubo menos posts que en 2025 en casi todos los temas | Se usan **porcentajes** (% negativo, % del volumen), no cantidades |
| **Modelo**: RoBERTuito se entrenó con tuits | Puede fallar con ironía, jerga o contexto argentino | Se mide su precisión contra una muestra etiquetada a mano (ver abajo) |
| **Términos ambiguos** | "kuka" o "planero" también aparecen citados o en broma | El tema peyorativos se reporta como indicador de clima, no como conteo de insultos |

## Métricas

### % negativo
Posts clasificados como negativos sobre el total de **posts útiles** del tema en el período.
Los posts sin texto analizable (solo un link o un emoji) cuentan para el volumen pero no
para el sentimiento.

### Intervalo de confianza (95 %, método de Wilson)
Cada % negativo lleva un rango. Por ejemplo, "40 % (27 %–55 %)" quiere decir que, con los
posts disponibles, el valor real podría estar razonablemente en cualquier punto de ese rango.

Se usa Wilson y no la fórmula clásica `p ± 1,96·√(p(1−p)/n)` porque esta última falla con
muestras chicas o porcentajes cercanos a 0 o 100 (puede dar rangos negativos o mayores a 100 %).

$$\frac{\hat p + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat p(1-\hat p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}, \quad z = 1{,}96$$

### Poca muestra
Si un período tiene menos de 30 posts útiles, se marca `poca_muestra`. El tablero lo muestra
atenuado. Para temas chicos (AySA, servicios públicos, Jorge Macri) conviene usar la vista mensual.

### ¿El cambio entre semanas es real?
Si los intervalos de dos semanas se superponen mucho, la diferencia puede ser ruido. Para
afirmarlo se compara con un test de diferencia de proporciones (p-valor < 0,05).

### % del volumen
Qué parte de todos los posts recolectados en la semana corresponde al tema. Corrige la caída
general de actividad de la plataforma: si un tema pasa de 1 % a 3 % del volumen, creció en
atención aunque la cantidad absoluta baje.

## Reglas del tablero
1. Solo **semanas completas** (la semana en curso no se muestra).
2. Siempre **porcentajes con su intervalo**, nunca solo cantidades.
3. Los períodos con poca muestra se ven distintos.
4. La precisión del modelo, medida contra la muestra etiquetada a mano, figura en el tablero.

## Validación del modelo (pendiente)
Se etiquetan a mano unos 200 posts, estratificados por tema, sin ver la predicción del
modelo. Se reportan F1 por clase y la matriz de confusión. Si el modelo confunde
sistemáticamente alguna clase (por ejemplo, ironía leída como positiva), se aclara en el tablero.
