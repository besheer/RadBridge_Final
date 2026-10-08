import test from 'node:test';
import assert from 'node:assert/strict';
import { quotationContext,quotationMeasurements,sameQuotationImage } from './viewerQuotation.mjs';
const ctx={orderId:1,studyUID:'1.2.3',imageId:'synthetic-frame-2',viewportId:'view-1'};
function fixture(study='1.2.3') {
 const services={viewportGridService:{getState:()=>({activeViewportId:'view-1',viewports:new Map([['view-1',{displaySetInstanceUIDs:['set-1']} ]])})},
  cornerstoneViewportService:{getCornerstoneViewport:()=>({getCurrentImageId:()=>ctx.imageId,element:{synthetic:true}})},
  displaySetService:{getDisplaySetByUID:()=>({StudyInstanceUID:study})}};
 return {services,data:{ok:true,order:{id:1,study_instance_uid:'1.2.3'}}};
}
test('loaded authorized study binds the selected image',()=>{const f=fixture();assert.equal(quotationContext(f.services,f.data).imageId,ctx.imageId);});
test('another study never becomes a report quotation',()=>{const f=fixture('9.8.7');assert.throws(()=>quotationContext(f.services,f.data),/outside this report/);});
test('missing report authorization fails closed',()=>{const f=fixture();assert.throws(()=>quotationContext(f.services,{...f.data,ok:false}),/authorized/);});
test('missing active image fails closed',()=>{const f=fixture();f.services.cornerstoneViewportService.getCornerstoneViewport=()=>({element:{}});assert.throws(()=>quotationContext(f.services,f.data),/loaded 2D image/);});
test('mixed display sets cannot bypass the study check',()=>{const f=fixture();f.services.viewportGridService.getState=()=>({activeViewportId:'view-1',viewports:new Map([['view-1',{displaySetInstanceUIDs:['set-1','foreign']} ]])});f.services.displaySetService.getDisplaySetByUID=id=>({StudyInstanceUID:id==='foreign'?'9.8.7':'1.2.3'});assert.throws(()=>quotationContext(f.services,f.data),/outside this report/);});
test('image switch is detected including frame and order',()=>{assert.ok(sameQuotationImage(ctx,{...ctx}));for(const [key,value] of Object.entries({imageId:'frame-3',studyUID:'9.8.7',orderId:2,viewportId:'view-2'}))assert.equal(sameQuotationImage(ctx,{...ctx,[key]:value}),false);});
test('copy retains displayed units and zero values without recomputation',()=>{const m={referenceStudyUID:ctx.studyUID,referencedImageId:ctx.imageId,toolName:'Length',displayText:{primary:['0 mm'],secondary:['S: 1 I: 2']}};assert.equal(quotationMeasurements([m],ctx),'Length: 0 mm [S: 1 I: 2]');});
test('foreign frame, study, invisible and uncomputed measurements are excluded',()=>{const m={referenceStudyUID:ctx.studyUID,referencedImageId:ctx.imageId,toolName:'Length',displayText:{primary:['12 mm'],secondary:[]}};assert.equal(quotationMeasurements([{...m,referenceStudyUID:'9.8.7'},{...m,referencedImageId:'other-frame'},{...m,isVisible:false},{...m,displayText:{primary:[]}}],ctx),'');});
test('annotation text is preserved as text, and control characters are flattened',()=>{const m={referenceStudyUID:ctx.studyUID,referencedImageId:ctx.imageId,toolName:'ArrowAnnotate',label:'SYNTHETIC\nNote',displayText:{primary:[]}};assert.equal(quotationMeasurements([m],ctx),'ArrowAnnotate: SYNTHETIC Note');});
