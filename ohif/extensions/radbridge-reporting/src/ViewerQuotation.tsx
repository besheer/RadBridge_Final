import React, { useEffect, useRef, useState } from 'react';
import html2canvas from 'html2canvas';
import { quotationContext, quotationMeasurements, sameQuotationImage } from './viewerQuotation.mjs';

export default function ViewerQuotation({ servicesManager, reportData }: { servicesManager: any; reportData: any }) {
  const [capture, setCapture] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const generation = useRef(0);
  const preview = useRef('');
  const services = servicesManager?.services || {};
  const clear = () => {
    generation.current++;
    if (preview.current) URL.revokeObjectURL(preview.current);
    preview.current = '';
    setCapture(null);
    setBusy(false);
  };
  useEffect(() => { clear(); setMessage(''); return () => { generation.current++; if (preview.current) URL.revokeObjectURL(preview.current); }; }, [reportData?.order?.id, reportData?.order?.study_instance_uid]);
  const button = { padding: '8px', margin: '4px 2px', border: '1px solid #64748b', borderRadius: 5, background: '#17394a', color: 'white' };

  async function takeCapture() {
    clear(); const current = generation.current; setBusy(true); setMessage('');
    try {
      const context = quotationContext(services, reportData);
      const text = quotationMeasurements(services.measurementService?.getMeasurements?.() || [], context);
      const rect = context.element.getBoundingClientRect();
      if (!rect.width || !rect.height) throw new Error('The active image is not visible.');
      const canvas = await html2canvas(context.element, { backgroundColor: '#000000', scale: Math.min(1, 1600 / Math.max(rect.width, rect.height)), logging: false, allowTaint: false });
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('Image capture failed.')), 'image/png'));
      if (current !== generation.current) return;
      if (!sameQuotationImage(context, quotationContext(services, reportData))) throw new Error('The image changed during capture. Capture it again.');
      if (text !== quotationMeasurements(services.measurementService?.getMeasurements?.() || [], context)) throw new Error('The annotations changed during capture. Capture them again.');
      if (blob.size > 16 * 1024 * 1024) throw new Error('The captured image is too large. Use Export active image.');
      preview.current = URL.createObjectURL(blob);
      setCapture({ blob, text, context, url: preview.current });
      setMessage('راجع اللقطة والقياسات قبل النقل / Review the image and measurements before copying.');
    } catch (error: any) { setMessage(error.message || 'Capture failed.'); }
    finally { if (current === generation.current) setBusy(false); }
  }

  function currentCapture() {
    if (!capture || !sameQuotationImage(capture.context, quotationContext(services, reportData))) throw new Error('Select the captured image again, or capture the current image.');
    return capture;
  }

  async function copyImage() {
    try {
      const quote = currentCapture();
      if (!navigator.clipboard?.write || !window.ClipboardItem) throw new Error('Clipboard image access is unavailable. Download PNG, then use Insert → Image in ONLYOFFICE.');
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': quote.blob })]);
      setMessage('الصورة نُسخت؛ ضع المؤشر داخل التقرير واضغط Ctrl+V / Image copied. Place the cursor inside the report and press Ctrl+V.');
    } catch (error: any) { setMessage(error.message || 'Copy failed. Download PNG instead.'); }
  }

  async function copyMeasurements() {
    try {
      const quote = currentCapture();
      if (!quote.text) throw new Error('No visible measurements or annotations exist on this image.');
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard access is unavailable. Select and copy the preview text below.');
      await navigator.clipboard.writeText(quote.text);
      setMessage('القياسات نُسخت؛ راجع الوحدات ثم الصق داخل التقرير / Measurements copied. Review units, then paste inside the report.');
    } catch (error: any) { setMessage(error.message || 'Select and copy the preview text below.'); }
  }

  function download() {
    try {
      const quote = currentCapture();
      const link = document.createElement('a'); link.href = quote.url; link.download = `report-image-${quote.context.orderId}.png`; link.click();
    } catch (error: any) { setMessage(error.message); }
  }

  return <section style={{ marginTop: 8 }} aria-label="Viewer quotation">
    <p>اقتباس صورة وقياسات إلى التقرير / Quote an image and measurements into the report.</p>
    <p>ضع المؤشر في محتوى التقرير، ثم الصق كل اقتباس. احتفظ ببيانات المريض ورقم الفحص. / Paste each quotation at the report cursor; preserve the patient and accession fields.</p>
    <button type="button" style={button} disabled={busy || !reportData?.ok} onClick={takeCapture}>التقاط ومعاينة / Capture &amp; preview</button>
    {capture && <div>
      <img src={capture.url} alt="Selected study image quotation" style={{ width: '100%', height: 'auto', marginTop: 8 }} />
      <button type="button" style={button} onClick={copyImage}>نسخ الصورة / Copy image</button>
      <button type="button" style={button} onClick={download}>تنزيل PNG / Download PNG</button>
      <label style={{ display: 'block' }}>القياسات والنص / Measurements &amp; text
        <textarea readOnly value={capture.text} style={{ width: '100%', minHeight: 100, boxSizing: 'border-box', color: '#111827', background: '#fff' }} />
      </label>
      <button type="button" style={button} disabled={!capture.text} onClick={copyMeasurements}>نسخ القياسات / Copy measurements</button>
    </div>}
    <p role="status" aria-live="polite">{message}</p>
    <small>لا يتم حفظ التقرير أو اعتماده تلقائيًا / Copying does not save or finalize the report.</small>
  </section>;
}
