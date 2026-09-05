window.config = {
  routerBasename: '/',
  showStudyList: true,

  extensions: [],
  modes: [],

  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'dicomweb',

      configuration: {
        friendlyName: 'RadBridge PACS',
        name: 'RadBridge Orthanc',

        qidoRoot: '/dicom-web',
        wadoRoot: '/dicom-web',
        wadoUriRoot: '/dicom-web',

        qidoSupportsIncludeField: true,
        supportsReject: false,

        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',

        enableStudyLazyLoad: true,
        supportsFuzzyMatching: true,
        supportsWildcard: true
      }
    }
  ],

  defaultDataSourceName: 'dicomweb'
};
