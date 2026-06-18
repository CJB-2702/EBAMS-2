# Initial Prompt

Captured verbatim (spelling preserved). Source of truth for *intent*.

---

> build an in depth mockup of how the assets application will look based off of
> the previous application in
> `asset_control_layer_starter_kit/initial_prompt.md`
> at localhost/assets
> review the app/presentation/assets
> app/presentation/core presentation and make a /starter-kit
> for the ui
>
> THE GOAL IS TO MAKE A MOCK APPLICATION WITH HARD CODED DATA in the shape of
> the new models that were migrated over and in the style of the current
> application so I can get a feel for how the new asset managment sub application
> will look without having to worry about the actual control logic and backend
> implementation on the current app
>
> 1 list out a map of all the new pages /routes that will be built and their
> anaologus previous pages
>
> let me review the flow and page structure before building, this should be a
> new starter kit assets_ui_plan_kit in the root directory

---

## Path interpretations (folder-correction rule applied)

- `app/presentation/assets` and `app/presentation/core` → the **old** Flask app's
  `/home/cb/REPOS/asset_management/app/presentation/routes/assets` and
  `.../routes/core` (+ their `templates/assets` and `templates/core`). The new
  Django app has no `app/presentation/`; UI lives per sub-app under
  `app/<app>/presentation_layer/` + `app/<app>/templates/`.
- "the previous application" → the old Flask app referenced by the control kit.

## Binding decisions from the request

1. **Mock only** — hard-coded data, no control/backend logic.
2. **New model shape** — data mirrors `app/assets/models/`.
3. **Current app style** — clone the `events` app shell.
4. **Served at `localhost/assets`** — real Django routes, fake data.
5. **Plan first** — produce this kit and pause for review of flow + page
   structure before building.
</content>
