// Local quotation only: no upload, report mutation, URL capability or storage.
export function quotationContext(services, reportData) {
  const order = reportData?.order;
  if (!reportData?.ok || !order?.id || !order.study_instance_uid) {
    throw new Error('Load the authorized RadBridge report first.');
  }
  const grid = services.viewportGridService?.getState();
  const viewportId = grid?.activeViewportId;
  const viewport = services.cornerstoneViewportService?.getCornerstoneViewport(viewportId);
  const imageId = viewport?.getCurrentImageId?.();
  const ids = grid?.viewports?.get(viewportId)?.displaySetInstanceUIDs;
  if (!viewport?.element || !imageId || !Array.isArray(ids) || !ids.length) {
    throw new Error('Select a loaded 2D image in the viewer first.');
  }
  const sets = ids.map(id => services.displaySetService?.getDisplaySetByUID(id));
  if (sets.some(set => !set || set.StudyInstanceUID !== order.study_instance_uid)) {
    throw new Error('The active image is outside this report study. Select its own study.');
  }
  return { orderId: order.id, studyUID: order.study_instance_uid, imageId, viewportId, element: viewport.element };
}

export function sameQuotationImage(a, b) {
  return Boolean(a && b && a.orderId === b.orderId && a.studyUID === b.studyUID && a.imageId === b.imageId && a.viewportId === b.viewportId);
}

export function quotationMeasurements(measurements, context) {
  const lines = [];
  for (const m of measurements || []) {
    if (m.referenceStudyUID !== context.studyUID || m.referencedImageId !== context.imageId || m.isVisible === false) continue;
    const primary = Array.isArray(m.displayText?.primary) ? m.displayText.primary : [];
    const secondary = Array.isArray(m.displayText?.secondary) ? m.displayText.secondary : [];
    const clean = value => String(value ?? '').replace(/[\r\n\x00-\x1f]+/g, ' ').trim();
    const value = primary.map(clean).filter(Boolean).join('; ');
    const label = clean(m.label);
    if (!value && !label) continue;
    const location = secondary.map(clean).filter(Boolean).join('; ');
    lines.push(`${clean(m.toolName) || 'Annotation'}: ${value}${label ? `${value ? ' — ' : ''}${label}` : ''}${location ? ` [${location}]` : ''}`);
  }
  return lines.join('\n');
}
