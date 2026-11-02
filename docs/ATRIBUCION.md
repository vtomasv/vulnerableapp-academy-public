# Atribución y alcance de la adaptación

VulnerableApp Academy y Mercado Cordillera son una adaptación estudiantil independiente para un taller local. Mercado Cordillera es un comercio ficticio: sus clientes, pedidos, precios CLP y despacho son material de entrenamiento. No procesa pagos ni representa a una empresa real.

## Aplicación vulnerable original

La base es **[SasanLabs/VulnerableApp](https://github.com/SasanLabs/VulnerableApp)**, proyecto **[OWASP VulnerableApp](https://owasp.org/projects/vulnerableapp)**. El código vendorizado mantiene su revisión registrada en `vendor/UPSTREAM_COMMIT`, los avisos originales y la licencia **Apache 2.0** en `vendor/LICENSE`.

El overlay agrega navegación, contexto comercial en español y un editor pedagógico sobre los endpoints reales. No modifica los controladores vulnerables vendorizados, los parámetros, niveles ni los criterios del catálogo. Las 189 misiones continúan disponibles; las prácticas sin criterio automático conservan su guía, no un XP inventado. La interfaz técnica original está disponible desde Kali en `http://target:9090/VulnerableApp/original/`; conserva textos originales en inglés.

## Harness y modelo

El motor del asistente es [S1N6H/pentest-harness](https://github.com/S1N6H/pentest-harness), fijado en el commit documentado en el repositorio. Se conserva su identidad y se añade un preset con herramientas y skills locales acotados, aprobación individual y evidencia evaluada por Academy. El modelo comunitario solicitado es `huihui_ai/Qwen3.8-abliterated:27b`, servido por Ollama dentro de Docker; esta adaptación no representa al autor del modelo ni garantiza sus respuestas.

## Contexto docente

El facilitador proporcionó como contexto su [enlace público de docentes del Magíster de Ingeniería en Seguridad de la Información](https://postgrados.umayor.cl/docentes/ingenieria-seguridad-informacion/) de Universidad Mayor. El enlace se incluye de forma factual, sin reproducir logos, sellos, retratos, biografías ni títulos no verificados.

No se afirma patrocinio, certificación o publicación oficial de esta adaptación por OWASP, SasanLabs, S1N6H o Universidad Mayor. Los enlaces y créditos deben conservarse en el portal, la tienda, la documentación y la web pública.
