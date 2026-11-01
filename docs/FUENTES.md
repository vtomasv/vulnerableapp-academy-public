# Procedencia

El código original incorporado proviene de SasanLabs/VulnerableApp, commit `4df80bbcd42682ecf26334f12c568e0f4a326c1a`, consultado el 1 de noviembre de 2026. Se conserva su licencia MIT en `vendor/LICENSE`.

El Compose original ya incluía Ollama, un inicializador de `phi3:mini`, `nomic-embed-text`, LLMForge, aplicaciones Java/JSP/PHP, MongoDB y Mailpit. Esta adaptación centra el taller en todas las familias del repositorio **Java VulnerableApp**, con su interfaz original, y añade portal pedagógico, Kali y tutor. No se afirma cobertura de aplicaciones separadas JSP/PHP ni de LLMForge: son repositorios diferentes.

Qwen3 ofrece herramientas y variantes locales; elegimos `huihui_ai/qwen3-abliterated:4b-v2-q4_K_M` por portabilidad CPU. No se aplica una modificación destinada a quitar sus salvaguardas. La seguridad operacional se impone en el harness y la red, no mediante confianza en el modelo.

## Referencias

[1]: https://github.com/SasanLabs/VulnerableApp "Repositorio oficial de VulnerableApp"
[2]: https://sasanlabs.github.io/VulnerableApp "Sitio y documentación de VulnerableApp"
[3]: https://ollama.com/library/qwen3 "Familia Qwen3 en Ollama"
[4]: https://docs.ollama.com/capabilities/tool-calling "API de llamadas de herramientas de Ollama"
[5]: https://www.kali.org/docs/containers/official-kalilinux-docker-images/ "Imágenes oficiales de Kali para Docker"
[6]: https://github.com/novnc/noVNC "noVNC y proxy WebSocket"

## Variante local del modelo

Modelo predeterminado: `huihui_ai/qwen3-abliterated:4b-v2-q4_K_M` (artefacto publicado aproximadamente 2,5 GB; admite herramientas y thinking según la ficha). El autor lo describe como uncensored mediante abliteration, pero advierte que es experimental y no tiene garantías de seguridad. «Sin restricciones» no significa que nunca rechace una petición ni que sea correcto. El harness impone restricciones externas independientemente del modelo.

Fuentes verificadas: https://ollama.com/huihui_ai/qwen3-abliterated:4b-v2-q4_K_M y https://ollama.com/huihui_ai/qwen3-abliterated. Alternativa oficial: `OLLAMA_MODEL=qwen3:4b`.
