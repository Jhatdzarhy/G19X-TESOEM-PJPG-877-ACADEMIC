<%-- Entrada de la aplicacion: el filtro de seguridad envia a /login si no hay sesion. --%>
<%@ page contentType="text/html; charset=UTF-8" session="false" %>
<% response.sendRedirect(request.getContextPath() + "/resumen"); %>