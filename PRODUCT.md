# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Personal administrativo y contable que recibe facturas por correo, revisa documentos pendientes y causa facturas en Alegra.

## Product Purpose

SyncBank centraliza la recepción, validación, revisión y causación de facturas electrónicas. El resultado correcto es que el usuario pueda detectar pendientes y errores rápidamente, revisar los datos extraídos y completar la operación sin salir del panel.

## Operating Context

La aplicación procesa correos IMAP y archivos XML, ZIP y PDF. Usa PostgreSQL como fuente de datos y Alegra como destino contable. Se ejecuta como una aplicación FastAPI + React desplegada en Railway.

## Capabilities and Constraints

- Monitorear facturas recibidas, pendientes, causadas y con error.
- Sincronizar manualmente el buzón además del procesamiento programado.
- Revisar facturas y documentos PDF pendientes antes de confirmar.
- Gestionar contactos, mapeos contables y registros de auditoría.
- Conservar una interfaz responsive y accesible para escritorio y móvil.

## Brand Commitments

El nombre del producto es SyncBank. La interfaz debe sentirse limpia, profesional y propia de una mesa de operaciones financieras.

## Evidence on Hand

El repositorio contiene datos y flujos reales de facturas, contactos, configuración y auditoría. No deben inventarse métricas, clientes ni resultados.

## Product Principles

- Priorizar el estado de la operación sobre la decoración.
- Mostrar siempre carga, error, vacío y recuperación.
- Usar lenguaje claro y acciones explícitas.
- Mantener la solución pequeña, directa y operable.
