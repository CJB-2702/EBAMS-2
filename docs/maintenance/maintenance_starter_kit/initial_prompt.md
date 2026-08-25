# Initial Prompt & Request Context

## Original User Request

> I want to mostly faithfully import the maintenance application from my previous application at
> `~home/repos/asset_managment/app/<layername>/Maintenance`
> a few things I want changed:
> there was a template builder in progress table
> I now want this replaced with session memory instead
> 
> review the data layer for maintenance
> there should be some differences between what the maintenance layer refrences and what currently exists lets outline the data model translation document first
> /kit-builder

## Key Constraints & Directives

1. **Source Codebase**: Legacy Flask/SQLAlchemy codebase located at `/home/cb/REPOS/asset_management/`.
2. **Target Architecture**: EBAMS-2 (Django 6.x server-rendered, Bulma + HTMX, layered OOP architecture, `AuditFieldsMixin`, `SoftDeleteMixin`, `Domain` row-level access control).
3. **Template Builder Draft Storage**: Eliminate legacy `TemplateBuilderMemory` DB table. Replace with session-backed draft memory (`request.session`).
4. **Data Layer Translation**: Re-align legacy maintenance references (`Event`, `Asset`, `PartDemand`, `User`, `Domain`, `MeterHistory`) to EBAMS-2 standard domain models and links.
5. **Phase**: Kit Builder Initialization (Starter Kit creation).
