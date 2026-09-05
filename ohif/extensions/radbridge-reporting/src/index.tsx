import { Types } from '@ohif/core';
import { id } from './id';
import getPanelModule from './getPanelModule';

const extension: Types.Extensions.Extension = {
  id,
  getPanelModule,
};

export default extension;
