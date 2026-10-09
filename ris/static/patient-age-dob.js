(function () {
  function isoLocal(day) {
    const year = String(day.getFullYear()).padStart(4, '0');
    const month = String(day.getMonth() + 1).padStart(2, '0');
    const date = String(day.getDate()).padStart(2, '0');
    return `${year}-${month}-${date}`;
  }

  function subtractMonths(today, months) {
    const originalDay = today.getDate();
    const result = new Date(today.getFullYear(), today.getMonth(), 1);
    result.setMonth(result.getMonth() - months);
    const lastDay = new Date(
      result.getFullYear(),
      result.getMonth() + 1,
      0
    ).getDate();
    result.setDate(Math.min(originalDay, lastDay));
    return result;
  }

  function subtractYears(today, years) {
    const originalDay = today.getDate();
    const result = new Date(today.getFullYear() - years, today.getMonth(), 1);
    const lastDay = new Date(
      result.getFullYear(),
      result.getMonth() + 1,
      0
    ).getDate();
    result.setDate(Math.min(originalDay, lastDay));
    return result;
  }

  function fullAge(dob, today, unit) {
    if (unit === 'DAYS') {
      return Math.max(0, Math.floor((today - dob) / 86400000));
    }
    let months =
      (today.getFullYear() - dob.getFullYear()) * 12 +
      today.getMonth() - dob.getMonth();
    if (today.getDate() < dob.getDate()) months -= 1;
    months = Math.max(0, months);
    return unit === 'MONTHS' ? months : Math.floor(months / 12);
  }

  function wire(group) {
    const dob = group.querySelector('[data-rb-dob]');
    const age = group.querySelector('[data-rb-age]');
    const unit = group.querySelector('[data-rb-age-unit]');
    const estimated = group.querySelector('[data-rb-dob-estimated]');
    const status = group.querySelector('[data-rb-dob-status]');
    if (!dob || !age || !unit || !estimated) return;

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    dob.max = isoLocal(today);

    function showStatus() {
      if (!status) return;
      status.textContent = estimated.checked
        ? group.dataset.estimatedText
        : '';
    }

    function ageToDob() {
      if (age.value === '') return;
      const value = Number(age.value);
      if (!Number.isInteger(value) || value < 0) return;
      let result;
      if (unit.value === 'MONTHS') result = subtractMonths(today, value);
      else if (unit.value === 'DAYS') {
        result = new Date(today);
        result.setDate(result.getDate() - value);
      } else result = subtractYears(today, value);
      dob.value = isoLocal(result);
      estimated.checked = true;
      showStatus();
    }

    function dobToAge() {
      if (!dob.value) {
        age.value = '';
        estimated.checked = false;
        showStatus();
        return;
      }
      const parts = dob.value.split('-').map(Number);
      const parsed = new Date(parts[0], parts[1] - 1, parts[2]);
      age.value = String(fullAge(parsed, today, unit.value));
      estimated.checked = false;
      showStatus();
    }

    age.addEventListener('input', ageToDob);
    unit.addEventListener('change', function () {
      if (estimated.checked && age.value !== '') ageToDob();
      else if (dob.value) dobToAge();
    });
    dob.addEventListener('change', dobToAge);
    estimated.addEventListener('change', showStatus);

    if (age.value !== '' && estimated.checked) ageToDob();
    else if (dob.value) {
      const wasEstimated = estimated.checked;
      dobToAge();
      estimated.checked = wasEstimated;
      showStatus();
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-rb-age-dob]').forEach(wire);
  });
})();
