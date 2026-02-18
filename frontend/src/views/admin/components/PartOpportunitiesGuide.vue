<template>
  <v-dialog :model-value="modelValue" max-width="900" scrollable @update:model-value="$emit('update:modelValue', $event)">
    <v-card>
      <v-card-title class="bg-purple text-white d-flex justify-space-between">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-help-circle</v-icon>
          {{ $t('admin.partGuide.title') }}
        </div>
        <v-btn icon variant="text" color="white" @click="$emit('update:modelValue', false)">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-0">
        <v-tabs v-model="guideTab" color="purple" grow>
          <v-tab value="overview">{{ $t('admin.partGuide.tabOverview') }}</v-tab>
          <v-tab value="dpmo">{{ $t('admin.partGuide.tabDpmo') }}</v-tab>
          <v-tab value="howto">{{ $t('admin.partGuide.tabHowTo') }}</v-tab>
          <v-tab value="examples">{{ $t('admin.partGuide.tabExamples') }}</v-tab>
        </v-tabs>

        <v-tabs-window v-model="guideTab" class="pa-4">
          <!-- Overview Tab -->
          <v-tabs-window-item value="overview">
            <v-alert type="info" variant="tonal" class="mb-4">
              <strong>{{ $t('admin.partGuide.whatAreTitle') }}</strong><br>
              {{ $t('admin.partGuide.whatAreDescription') }}
            </v-alert>

            <h4 class="mb-3">{{ $t('admin.partGuide.whyMatter') }}</h4>
            <v-list density="compact">
              <v-list-item prepend-icon="mdi-target">
                <v-list-item-title><strong>{{ $t('admin.partGuide.qualityMeasurement') }}</strong></v-list-item-title>
                <v-list-item-subtitle>{{ $t('admin.partGuide.qualityMeasurementDesc') }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item prepend-icon="mdi-compare">
                <v-list-item-title><strong>{{ $t('admin.partGuide.fairComparison') }}</strong></v-list-item-title>
                <v-list-item-subtitle>{{ $t('admin.partGuide.fairComparisonDesc') }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item prepend-icon="mdi-chart-line">
                <v-list-item-title><strong>{{ $t('admin.partGuide.sigmaLevel') }}</strong></v-list-item-title>
                <v-list-item-subtitle>{{ $t('admin.partGuide.sigmaLevelDesc') }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>

            <v-divider class="my-4" />

            <h4 class="mb-3">{{ $t('admin.partGuide.summaryCardsExplained') }}</h4>
            <v-row>
              <v-col cols="6" md="3">
                <v-card variant="tonal" color="primary" class="text-center pa-2">
                  <v-icon>mdi-counter</v-icon>
                  <div class="text-caption">{{ $t('admin.totalParts') }}</div>
                  <div class="text-body-2">{{ $t('admin.partGuide.totalPartsDesc') }}</div>
                </v-card>
              </v-col>
              <v-col cols="6" md="3">
                <v-card variant="tonal" color="info" class="text-center pa-2">
                  <v-icon>mdi-calculator</v-icon>
                  <div class="text-caption">{{ $t('admin.avgOpportunities') }}</div>
                  <div class="text-body-2">{{ $t('admin.partGuide.avgOpportunitiesDesc') }}</div>
                </v-card>
              </v-col>
              <v-col cols="6" md="3">
                <v-card variant="tonal" color="success" class="text-center pa-2">
                  <v-icon>mdi-arrow-down</v-icon>
                  <div class="text-caption">{{ $t('admin.minOpportunities') }}</div>
                  <div class="text-body-2">{{ $t('admin.partGuide.simplestProduct') }}</div>
                </v-card>
              </v-col>
              <v-col cols="6" md="3">
                <v-card variant="tonal" color="warning" class="text-center pa-2">
                  <v-icon>mdi-arrow-up</v-icon>
                  <div class="text-caption">{{ $t('admin.maxOpportunities') }}</div>
                  <div class="text-body-2">{{ $t('admin.partGuide.mostComplexProduct') }}</div>
                </v-card>
              </v-col>
            </v-row>
          </v-tabs-window-item>

          <!-- DPMO Calculation Tab -->
          <v-tabs-window-item value="dpmo">
            <h4 class="mb-3">{{ $t('admin.partGuide.understandingDpmo') }}</h4>
            <v-alert type="success" variant="tonal" class="mb-4">
              <strong>{{ $t('admin.partGuide.dpmoFormula') }}:</strong><br>
              <code class="text-h6">DPMO = (Defects x 1,000,000) / (Units x Opportunities per Unit)</code>
            </v-alert>

            <h4 class="mb-3">{{ $t('admin.partGuide.exampleCalc') }}</h4>
            <v-card variant="outlined" class="mb-4 pa-4">
              <v-row>
                <v-col cols="12" md="6">
                  <p><strong>{{ $t('admin.partGuide.given') }}:</strong></p>
                  <ul>
                    <li>{{ $t('admin.partGuide.unitsProduced') }}: 1,000</li>
                    <li>{{ $t('admin.partGuide.defectsFound') }}: 15</li>
                    <li>{{ $t('admin.partGuide.oppPerUnit') }}: 20</li>
                  </ul>
                </v-col>
                <v-col cols="12" md="6">
                  <p><strong>{{ $t('admin.partGuide.calculation') }}:</strong></p>
                  <p>{{ $t('admin.partGuide.totalOpp') }} = 1,000 x 20 = 20,000</p>
                  <p>DPMO = (15 x 1,000,000) / 20,000</p>
                  <p class="text-h6 text-primary">DPMO = 750</p>
                </v-col>
              </v-row>
            </v-card>

            <h4 class="mb-3">{{ $t('admin.partGuide.sigmaReference') }}</h4>
            <v-table density="compact">
              <thead>
                <tr>
                  <th>{{ $t('admin.partGuide.sigmaLevel') }}</th>
                  <th>DPMO</th>
                  <th>{{ $t('admin.partGuide.yield') }} %</th>
                  <th>{{ $t('admin.partGuide.rating') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>6&#x3C3;</td>
                  <td>3.4</td>
                  <td>99.99966%</td>
                  <td><v-chip size="small" color="success">{{ $t('admin.partGuide.worldClass') }}</v-chip></td>
                </tr>
                <tr>
                  <td>5&#x3C3;</td>
                  <td>233</td>
                  <td>99.977%</td>
                  <td><v-chip size="small" color="success">{{ $t('admin.partGuide.excellent') }}</v-chip></td>
                </tr>
                <tr>
                  <td>4&#x3C3;</td>
                  <td>6,210</td>
                  <td>99.379%</td>
                  <td><v-chip size="small" color="info">{{ $t('admin.partGuide.good') }}</v-chip></td>
                </tr>
                <tr>
                  <td>3&#x3C3;</td>
                  <td>66,807</td>
                  <td>93.32%</td>
                  <td><v-chip size="small" color="warning">{{ $t('common.average') }}</v-chip></td>
                </tr>
                <tr>
                  <td>2&#x3C3;</td>
                  <td>308,538</td>
                  <td>69.15%</td>
                  <td><v-chip size="small" color="error">{{ $t('admin.partGuide.poor') }}</v-chip></td>
                </tr>
              </tbody>
            </v-table>

            <v-alert type="warning" variant="tonal" class="mt-4">
              <strong>{{ $t('admin.partGuide.important') }}:</strong> {{ $t('admin.partGuide.accuracyWarning') }}
            </v-alert>
          </v-tabs-window-item>

          <!-- How To Use Tab -->
          <v-tabs-window-item value="howto">
            <h4 class="mb-3">{{ $t('admin.partGuide.addingNewPart') }}</h4>
            <v-stepper :items="stepperItems" alt-labels class="elevation-0 mb-4">
              <template v-slot:item.1>
                <v-card flat>
                  <v-card-text>
                    <p>{{ $t('admin.partGuide.step1Click') }}</p>
                  </v-card-text>
                </v-card>
              </template>
              <template v-slot:item.2>
                <v-card flat>
                  <v-card-text>
                    <ul>
                      <li><strong>{{ $t('admin.partGuide.fieldPartNumber') }}:</strong> {{ $t('admin.partGuide.fieldPartNumberDesc') }}</li>
                      <li><strong>{{ $t('admin.partGuide.fieldOppPerUnit') }}:</strong> {{ $t('admin.partGuide.fieldOppPerUnitDesc') }}</li>
                      <li><strong>{{ $t('admin.partGuide.fieldDescription') }}:</strong> {{ $t('admin.partGuide.fieldDescriptionDesc') }}</li>
                      <li><strong>{{ $t('admin.partGuide.fieldComplexity') }}:</strong> {{ $t('admin.partGuide.fieldComplexityDesc') }}</li>
                    </ul>
                  </v-card-text>
                </v-card>
              </template>
              <template v-slot:item.3>
                <v-card flat>
                  <v-card-text>
                    <p>{{ $t('admin.partGuide.step3Review') }}</p>
                    <p>{{ $t('admin.partGuide.step3Available') }}</p>
                  </v-card-text>
                </v-card>
              </template>
            </v-stepper>

            <v-divider class="my-4" />

            <h4 class="mb-3">{{ $t('admin.partGuide.csvFormat') }}</h4>
            <v-alert type="info" variant="tonal" class="mb-3">
              {{ $t('admin.partGuide.csvFormatHint') }}
            </v-alert>
            <v-table density="compact">
              <thead>
                <tr>
                  <th>{{ $t('admin.partGuide.column') }}</th>
                  <th>{{ $t('common.required') }}</th>
                  <th>{{ $t('common.description') }}</th>
                  <th>{{ $t('admin.partGuide.example') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>part_number</td>
                  <td><v-icon color="success">mdi-check</v-icon></td>
                  <td>{{ $t('admin.partGuide.csvPartNumberDesc') }}</td>
                  <td>PART-001</td>
                </tr>
                <tr>
                  <td>opportunities_per_unit</td>
                  <td><v-icon color="success">mdi-check</v-icon></td>
                  <td>{{ $t('admin.partGuide.csvOppDesc') }}</td>
                  <td>15</td>
                </tr>
                <tr>
                  <td>part_description</td>
                  <td><v-icon color="grey">mdi-minus</v-icon></td>
                  <td>{{ $t('admin.partGuide.csvDescDesc') }}</td>
                  <td>Standard T-Shirt</td>
                </tr>
                <tr>
                  <td>complexity</td>
                  <td><v-icon color="grey">mdi-minus</v-icon></td>
                  <td>{{ $t('admin.partGuide.csvComplexityDesc') }}</td>
                  <td>Standard</td>
                </tr>
                <tr>
                  <td>notes</td>
                  <td><v-icon color="grey">mdi-minus</v-icon></td>
                  <td>{{ $t('admin.partGuide.csvNotesDesc') }}</td>
                  <td>Basic garment</td>
                </tr>
              </tbody>
            </v-table>

            <v-divider class="my-4" />

            <h4 class="mb-3">{{ $t('admin.partGuide.determiningCount') }}</h4>
            <p class="mb-3">{{ $t('admin.partGuide.determiningCountDesc') }}</p>
            <ul>
              <li>{{ $t('admin.partGuide.checkStitching') }}</li>
              <li>{{ $t('admin.partGuide.checkMaterial') }}</li>
              <li>{{ $t('admin.partGuide.checkDimensional') }}</li>
              <li>{{ $t('admin.partGuide.checkFinishing') }}</li>
              <li>{{ $t('admin.partGuide.checkAssembly') }}</li>
              <li>{{ $t('admin.partGuide.checkLabeling') }}</li>
            </ul>
          </v-tabs-window-item>

          <!-- Examples Tab -->
          <v-tabs-window-item value="examples">
            <h4 class="mb-3">{{ $t('admin.partGuide.industryExamples') }}</h4>

            <v-expansion-panels>
              <v-expansion-panel :title="$t('admin.partGuide.exTshirt')">
                <v-expansion-panel-text>
                  <v-table density="compact">
                    <tbody>
                      <tr><td>{{ $t('admin.partGuide.collarStitching') }}</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.shoulderSeams') }} (2)</td><td>4 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.sideSeams') }} (2)</td><td>4 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.sleeveAttachment') }} (2)</td><td>4 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.sleeveHem') }} (2)</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.bottomHem') }}</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.labelAttachment') }}</td><td>1 {{ $t('admin.partGuide.opportunity') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.printDecoration') }}</td><td>3 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr class="font-weight-bold"><td>{{ $t('common.total') }}</td><td>22 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                    </tbody>
                  </v-table>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel :title="$t('admin.partGuide.exBoot')">
                <v-expansion-panel-text>
                  <v-table density="compact">
                    <tbody>
                      <tr><td>{{ $t('admin.partGuide.upperStitching') }}</td><td>8 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.soleAttachment') }}</td><td>4 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.heelAttachment') }}</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.laceHoles') }} (12)</td><td>12 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.tongueAttachment') }}</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.innerLining') }}</td><td>4 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.logoBranding') }}</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.finishing') }}</td><td>3 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr class="font-weight-bold"><td>{{ $t('common.total') }}</td><td>37 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                    </tbody>
                  </v-table>
                </v-expansion-panel-text>
              </v-expansion-panel>

              <v-expansion-panel :title="$t('admin.partGuide.exBelt')">
                <v-expansion-panel-text>
                  <v-table density="compact">
                    <tbody>
                      <tr><td>{{ $t('admin.partGuide.buckleAttachment') }}</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.strapMaterial') }}</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.stitching') }}</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.holes') }} (5)</td><td>5 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr><td>{{ $t('admin.partGuide.edgeFinishing') }}</td><td>2 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                      <tr class="font-weight-bold"><td>{{ $t('common.total') }}</td><td>13 {{ $t('admin.partGuide.opportunities') }}</td></tr>
                    </tbody>
                  </v-table>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <v-divider class="my-4" />

            <v-alert type="success" variant="tonal">
              <strong>{{ $t('admin.partGuide.tip') }}:</strong> {{ $t('admin.partGuide.tipText') }}
            </v-alert>
          </v-tabs-window-item>
        </v-tabs-window>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn color="purple" @click="$emit('update:modelValue', false)">{{ $t('common.close') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:modelValue'])

const guideTab = ref('overview')

const stepperItems = computed(() => [
  t('admin.partGuide.stepClickAdd'),
  t('admin.partGuide.stepFillForm'),
  t('common.save')
])
</script>
