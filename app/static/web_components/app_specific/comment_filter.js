// Small deliberate JS exception: Human/All/Machine comment-filter buttons on
// events/fragments/comments_card.html, scoped to the nearest .card ancestor
// so multiple comments cards on one page (parts revisions, supplier items,
// asset model versions, multiple event cards in a list, ...) stay independent
// of one another. One shared file so every app renders the same behavior —
// see events/fragments/comments_card.html.
window.__filterComments = function (evt, btn, filter) {
  evt.preventDefault();
  var group = btn.closest(".comment-filter-group");
  var card = btn.closest(".card");
  group.querySelectorAll(".comment-filter-item").forEach(function (b) {
    b.classList.toggle("is-link", b === btn);
    b.classList.toggle("is-selected", b === btn);
    b.classList.toggle("is-light", b !== btn);
  });
  card.querySelectorAll("[data-comment-kind]").forEach(function (row) {
    row.style.display = filter === "all" || row.dataset.commentKind === filter ? "" : "none";
  });
  return false;
};
