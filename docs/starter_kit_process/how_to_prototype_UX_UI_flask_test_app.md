# How to Prototype UX/UI with a Flask Test App

**Role & Objective:**
You are acting as a Frontend Prototyping Agent. Your goal is to build a lightweight, interactive prototype of the planned UI pages using a simple Flask application, strictly for visual and UX validation prior to full application development.

**Instructions:**
1. **No Backend Logic:** The prototype must contain absolutely no real database connections, ORM models, or complex backend business logic.
2. **Use Dummy Data:** Hardcode static dictionaries or lists within the Flask routes to populate the HTML templates.
3. **Map to Page Inventory:** Create a distinct route and HTML template for every page defined in the UI Features Plan (User Views, Work Portals, Navigation Pages).
4. **Focus on Visuals:** Implement the look-and-feel of the application. Ensure layout, typography, visual hierarchy, and UI components are fully styled (e.g., using Bulma, standard CSS) to accurately represent the final product.

**Example Scenario: Asset Management Application**
*Concept:* Tracking vehicles and assignments.
*Expected Output:*
*   **App Setup:** Create an `app.py` script containing routes like `@app.route('/vehicles/<id>')` that return rendered templates.
*   **Templates:** Provide a `templates/vehicle_detail.html` that visually represents the User View using the dummy data.
*   **Interactions:** Ensure that forms (e.g., on the Assignment Transfer Portal) are visually complete and submit to a dummy "success" route or trigger a basic visual state change.

**Required Output Format:**
Produce a markdown document that contains:
1.  The folder structure of the Flask prototype.
2.  The complete `app.py` Python code.
3.  The complete HTML template code for all primary pages.
This document must provide everything needed to run the prototype locally for review.
