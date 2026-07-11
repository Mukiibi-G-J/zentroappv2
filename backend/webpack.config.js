const path = require('path');
const { VueLoaderPlugin } = require('vue-loader');
const webpack = require('webpack');

module.exports = {
  entry: {
    'item-journal': './static/src/item-journal.js',
  },
  output: {
    path: path.resolve(__dirname, 'static/js'),
    filename: '[name].js',
  },
  module: {
    rules: [
      {
        test: /\.vue$/,
        loader: 'vue-loader'
      },
      {
        test: /\.js$/,
        loader: 'babel-loader'
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      }
    ]
  },
  resolve: {
    alias: {
      'vue': 'vue/dist/vue.esm-bundler.js'
    },
    extensions: ['.js', '.vue']
  },
  plugins: [
    new VueLoaderPlugin(),
    new webpack.DefinePlugin({
      __VUE_OPTIONS_API__: true,
      __VUE_PROD_DEVTOOLS__: false,
      __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false
    })
  ]
}; 