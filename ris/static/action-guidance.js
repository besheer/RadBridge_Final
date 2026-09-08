(() => {
  function initializeGuidance() {
    document.querySelectorAll('.rb-action-guidance').forEach((wrapper, index) => {
      const trigger = wrapper.querySelector('.rb-guidance-trigger');
      const popover = wrapper.querySelector('.rb-guidance-popover');
      const close = wrapper.querySelector('.rb-guidance-close');
      if (!trigger || !popover) return;

      const id = `rb-action-guide-${index + 1}`;
      popover.id = id;
      trigger.setAttribute('popovertarget', id);
      trigger.setAttribute('aria-controls', id);

      if (close) {
        close.addEventListener('click', () => {
          if (typeof popover.hidePopover === 'function') {
            popover.hidePopover();
          } else {
            popover.removeAttribute('open');
          }
          trigger.focus();
        });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeGuidance);
  } else {
    initializeGuidance();
  }
})();
