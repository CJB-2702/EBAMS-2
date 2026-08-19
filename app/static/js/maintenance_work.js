/* Work portal dialog prefill.
 *
 * The page renders ONE dialog per kind of decision, not one per row — the
 * action list is re-rendered by htmx after every mutation, and dialogs living
 * inside a swapped fragment would be destroyed mid-interaction. Each trigger
 * button carries its row's values in data-* attributes; these handlers copy
 * them into the shared dialog just before the browser opens it.
 *
 * Opening is still done natively by commandfor/command (see
 * harness/UX_UI/design_patterns/modals.md) — nothing here calls showModal().
 * These handlers only fill fields.
 */
(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function data(el, name) {
    return el.getAttribute("data-" + name) || "";
  }

  /* The wall clock the SERVER uses, formatted for <input type="datetime-local">.
   *
   * The project runs in UTC (settings.TIME_ZONE), so every datetime rendered
   * into the page — a blocker's start_date, a limitation's start_time — is a
   * UTC wall clock, and the view parses these inputs back as UTC. Stamping
   * browser-local time here instead put the default "now" hours away from
   * those values: a technician in UTC-7 opening the resolve form got an end
   * time seven hours BEFORE the start time already in the field, and the
   * manager correctly refused it. Use UTC getters so both ends agree.
   */
  function nowLocal() {
    var d = new Date();
    var pad = function (n) {
      return String(n).padStart(2, "0");
    };
    return (
      d.getUTCFullYear() +
      "-" + pad(d.getUTCMonth() + 1) +
      "-" + pad(d.getUTCDate()) +
      "T" + pad(d.getUTCHours()) +
      ":" + pad(d.getUTCMinutes())
    );
  }

  /* ---------------------------------------------------------------- *
   * Step outcome: complete / fail / skip / block / reopen
   *
   * One dialog, five verbs. Every one of them requires a note, because
   * "why did this step end this way" is the only part of the record a
   * technician can supply and nobody else can reconstruct later.
   * ---------------------------------------------------------------- */
  var VERBS = {
    complete_action: {
      title: "Complete step",
      submit: "Mark complete",
      submitClass: "is-success",
      notesLabel: "Completion notes",
      billable: true,
    },
    fail_action: {
      title: "Fail step",
      submit: "Mark failed",
      submitClass: "is-danger",
      notesLabel: "Reason for failure",
      billable: true,
    },
    skip_action: {
      title: "Skip step",
      submit: "Skip step",
      submitClass: "is-warning",
      notesLabel: "Reason for skipping",
      billable: false,
    },
    block_action: {
      title: "Block step",
      submit: "Mark blocked",
      submitClass: "is-warning",
      notesLabel: "Reason work is blocked",
      billable: false,
    },
    reopen_action: {
      title: "Reopen step",
      submit: "Reopen step",
      submitClass: "is-info",
      notesLabel: "Reason for reopening",
      billable: false,
    },
  };

  /* Legacy generated a suggested comment per transition and let the user
     edit it. Same idea: a sentence that is true by default beats an empty
     required field the technician has to invent something for. */
  function suggestedNote(verb, from) {
    switch (verb) {
      case "complete_action":
        return "Action completed successfully";
      case "fail_action":
        return "Action failed";
      case "skip_action":
        return "Action skipped";
      case "block_action":
        return "Action blocked";
      case "reopen_action":
        return from === "Blocked"
          ? "Action resumed after being blocked"
          : "Action reset to In Progress";
      default:
        return "";
    }
  }

  window.prefillActionStatus = function (button) {
    var verb = data(button, "verb");
    var config = VERBS[verb];
    if (!config) return;

    var from = data(button, "current-status");

    $("action-status-verb").value = verb;
    $("action-status-id").value = data(button, "action-id");
    $("action-status-title").textContent = config.title;
    $("action-status-name").textContent = data(button, "action-name");
    $("action-status-current").textContent = from;
    $("action-status-notes-label").textContent = config.notesLabel;

    var notes = $("action-status-notes");
    notes.value = suggestedNote(verb, from);
    notes.placeholder = config.notesLabel;

    var billableField = $("action-status-billable-field");
    var billableInput = $("action-status-billable");
    billableField.hidden = !config.billable;
    billableInput.disabled = !config.billable;
    if (config.billable) {
      billableInput.value =
        data(button, "billable-hours") || data(button, "expected-hours") || "";
    }

    var submit = $("action-status-submit");
    submit.textContent = config.submit;
    submit.className = "button card-footer-primary " + config.submitClass;
  };

  /* ---------------------------------------------------------------- *
   * Step edit
   * ---------------------------------------------------------------- */
  window.prefillActionEdit = function (button) {
    $("action-edit-id").value = data(button, "action-id");
    $("action-edit-heading").textContent = data(button, "action-name");
    $("action-edit-name").value = data(button, "action-name");
    $("action-edit-description").value = data(button, "description");
    $("action-edit-instructions").value = data(button, "instructions");
    $("action-edit-safety").value = data(button, "safety-notes");
    $("action-edit-estimated").value = data(button, "estimated-minutes");
    $("action-edit-billable").value = data(button, "billable-hours");
    $("action-edit-completion-notes").value = data(button, "completion-notes");
  };

  /* ---------------------------------------------------------------- *
   * Add a part demand to a step
   * ---------------------------------------------------------------- */
  window.prefillAddPart = function (button) {
    $("action-part-id").value = data(button, "action-id");
    $("action-part-heading").textContent = data(button, "action-name");
    $("action-part-quantity").value = "1";
  };

  /* ---------------------------------------------------------------- *
   * Part demand: record qty issued
   *
   * Prefills qty issued with the demanded quantity — the common case is
   * "I took exactly what was asked for", and the technician overrides it
   * only when that is not what happened.
   * ---------------------------------------------------------------- */
  window.prefillIssueDemand = function (button) {
    var demanded = data(button, "quantity-requested");
    $("demand-issue-id").value = data(button, "demand-id");
    $("demand-issue-part").textContent = data(button, "part-name");
    $("demand-issue-demanded").textContent = demanded;
    $("demand-issue-qty").value = demanded;
  };

  /* ---------------------------------------------------------------- *
   * Part demand: edit quantity / priority / issuance
   * ---------------------------------------------------------------- */
  window.prefillUpdateDemand = function (button) {
    $("demand-update-id").value = data(button, "demand-id");
    $("demand-update-part").textContent = data(button, "part-name");
    $("demand-update-quantity").value = data(button, "quantity-requested");
    $("demand-update-priority").value = data(button, "priority");
    $("demand-update-issuance").value = data(button, "issuance-state");
    $("demand-update-qty-issued").value = "";
  };

  /* ---------------------------------------------------------------- *
   * Part demand: cancel (destructive — comment required)
   * ---------------------------------------------------------------- */
  window.prefillCancelDemand = function (button) {
    $("demand-cancel-id").value = data(button, "demand-id");
    $("demand-cancel-part").textContent = data(button, "part-name");
    $("demand-cancel-quantity").textContent = data(button, "quantity-requested");
    $("demand-cancel-notes").value = "";
  };

  /* ---------------------------------------------------------------- *
   * Part demand: manager rejection from the approval queue
   * ---------------------------------------------------------------- */
  window.prefillRejectDemand = function (button) {
    $("demand-reject-id").value = data(button, "demand-id");
    $("demand-reject-part").textContent = data(button, "part-name");
    $("demand-reject-notes").value = "";
  };

  /* ---------------------------------------------------------------- *
   * Resolving the two interruption types. Both take a mandatory reason:
   * an interruption record that opens with a stated cause and closes
   * with silence is only half a record.
   * ---------------------------------------------------------------- */
  window.prefillResolveBlocker = function (button) {
    $("blocker-resolve-id").value = data(button, "blocker-id");
    $("blocker-resolve-reason").textContent = data(button, "reason");
    $("blocker-resolve-priority").textContent = data(button, "priority");
    /* Start comes from the record so it can be corrected, not re-guessed;
       end defaults to now, which is the common case. */
    $("blocker-resolve-start").value = data(button, "start");
    $("blocker-resolve-end").value = nowLocal();
    $("blocker-resolve-lost").value = data(button, "hours-lost") || "0";
    $("blocker-resolve-update-notes").value = "";
    $("blocker-resolve-notes").value = "";
    $("blocker-resolve-comment").value = "";
  };

  window.prefillCloseLimitation = function (button) {
    $("limitation-close-id").value = data(button, "record-id");
    $("limitation-close-description").textContent = data(button, "description");
    $("limitation-close-status").textContent = data(button, "status");
    $("limitation-close-start").value = data(button, "start");
    $("limitation-close-end").value = nowLocal();
    $("limitation-close-notes").value = "";
    $("limitation-close-comment").value = "";
  };

  /* ---------------------------------------------------------------- *
   * datetime-local fields default to "now"
   *
   * Both interruption forms require a start time, and in practice it is
   * always the moment the person is filling the form in. Making them
   * hand-type today's date to record something happening in front of
   * them is friction with no upside — they can still change it.
   * ---------------------------------------------------------------- */
  function stampNowOnOpen(dialogId, fieldIds) {
    var dialog = $(dialogId);
    if (!dialog) return;
    /* `toggle` fires when the dialog opens or closes; only fill on open,
       and only when the field is empty so a re-open does not clobber
       something the user already typed. */
    dialog.addEventListener("toggle", function () {
      if (!dialog.open) return;
      fieldIds.forEach(function (id) {
        var el = $(id);
        if (el && !el.value) el.value = nowLocal();
      });
    });
  }

  /* ---------------------------------------------------------------- *
   * Capability limitation: temporary modifications become required when
   * the chosen status claims a compensation is in place — a claim of
   * compensation with no description of it is not a record of anything.
   * ---------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", function () {
    stampNowOnOpen("event-blocker-dialog", ["event-blocker-start"]);
    stampNowOnOpen("event-limitation-dialog", ["limitation-start"]);

    var status = $("limitation-status");
    var wrap = $("limitation-modifications-field");
    var input = $("limitation-modifications");
    if (!status || !wrap || !input) return;

    function sync() {
      var compensating = /temporary compensation/i.test(
        status.options[status.selectedIndex].textContent
      );
      wrap.hidden = !compensating;
      input.required = compensating;
      if (!compensating) input.value = "";
    }
    status.addEventListener("change", sync);
    sync();
  });
})();
