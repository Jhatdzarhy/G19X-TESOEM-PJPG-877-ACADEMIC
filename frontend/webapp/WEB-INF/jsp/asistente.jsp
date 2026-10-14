<%--
  Asistente de IA (CC-17, Modulo 6): chat de solo lectura sobre el motor analitico.
  La JSP solo pinta la estructura; js/asistente.js envia la pregunta a
  /api/asistente/mensajes (AsistenteServlet, usuario y rol de la sesion) y lee el
  historial por ApiLecturaServlet. La respuesta se construye con nodos de texto:
  solo se reconocen negritas y listas; nunca se interpreta HTML (XSS).
--%>
<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
<%@ include file="/WEB-INF/jsp/fragmentos/cabecera.jspf" %>
<%@ include file="/WEB-INF/jsp/fragmentos/ia-nav.jspf" %>

<header class="vista-encabezado">
    <div>
        <h1 class="titulo-vista">Asistente de IA</h1>
        <p class="vista-sub">Pregunta por los indicadores, las recomendaciones o el pronóstico. Responde con cifras consultadas al motor analítico.</p>
    </div>
    <div class="vista-frescura">
        <span class="etiqueta-origen">Solo lectura</span>
    </div>
</header>

<p class="aviso aviso-info asis-aviso" role="note">
    La IA puede equivocarse: verifica las cifras en el dashboard. Los datos operativos son simulados.
    El asistente no aprueba, compra ni cambia nada.
</p>

<div class="asis-cuerpo">
    <aside class="tarjeta asis-historial" aria-labelledby="titulo-historial">
        <button type="button" class="boton boton-principal asis-nueva" id="asis-nueva">Nueva conversación</button>
        <h2 class="det-subtitulo" id="titulo-historial">Conversaciones</h2>
        <ul class="asis-conversaciones" id="asis-conversaciones"></ul>
        <p class="texto-suave" id="asis-sin-historial" hidden>Aún no tienes conversaciones.</p>
    </aside>

    <section class="tarjeta asis-chat" aria-label="Conversación con el asistente">
        <p class="aviso aviso-error" id="asis-error" role="alert" hidden></p>

        <div class="asis-bienvenida" id="asis-bienvenida">
            <p class="asis-bienvenida-titulo">¿En qué te ayudo hoy?</p>
            <p class="texto-suave">Preguntas sugeridas:</p>
            <div class="asis-sugerencias" id="asis-sugerencias"></div>
        </div>

        <ol class="asis-mensajes" id="asis-mensajes" aria-live="polite"></ol>

        <form class="asis-formulario" id="asis-formulario" novalidate>
            <label class="visualmente-oculto" for="asis-pregunta">Tu pregunta</label>
            <textarea id="asis-pregunta" class="campo asis-pregunta" rows="2" maxlength="1000"
                      placeholder="Escribe tu pregunta. Enter envía; Mayús + Enter agrega una línea."></textarea>
            <div class="asis-acciones">
                <span class="texto-suave" id="asis-contador">0 / 1000</span>
                <button type="submit" class="boton boton-principal" id="asis-enviar">Enviar</button>
            </div>
        </form>
        <p class="texto-suave asis-modelos" id="asis-modelos"></p>
    </section>
</div>

<script src="${pageContext.request.contextPath}/js/comun.js?v=${sc:esc(version)}"></script>
<script src="${pageContext.request.contextPath}/js/asistente.js?v=${sc:esc(version)}"></script>

<%@ include file="/WEB-INF/jsp/fragmentos/pie.jspf" %>