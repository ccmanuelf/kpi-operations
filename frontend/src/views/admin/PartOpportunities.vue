<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-2">
          <v-icon class="mr-2">mdi-chart-scatter-plot</v-icon>
          {{ $t('admin.partOpportunities') }}
        </h1>
        <p class="text-subtitle-1 text-grey">
          {{ $t('admin.partOpportunitiesDescription') }}
        </p>
      </v-col>
    </v-row>

    <!-- Info Card -->
    <v-row class="mt-2">
      <v-col cols="12">
        <v-alert type="info" variant="tonal" density="compact">
          <v-icon class="mr-2">mdi-information</v-icon>
          {{ $t('admin.partOpportunitiesInfo') }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- Actions and Filters -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clientOptions"
          item-title="client_name"
          item-value="client_id"
          :label="$t('filters.client')"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-domain"
          clearable
          @update:model-value="loadPartOpportunities"
        />
      </v-col>
      <v-col cols="12" md="8" class="d-flex align-center gap-2">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          @click="openCreateDialog"
        >
          {{ $t('admin.addPartOpportunity') }}
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-upload"
          @click="openUploadDialog"
        >
          {{ $t('csv.upload') }}
        </v-btn>
        <v-btn
          color="info"
          prepend-icon="mdi-download"
          variant="outlined"
          @click="downloadTemplate"
        >
          {{ $t('csv.downloadTemplate') }}
        </v-btn>
        <v-btn
          color="purple"
          prepend-icon="mdi-help-circle"
          variant="outlined"
          @click="showGuide = true"
        >
          {{ $t('admin.floatingPool.howToUse') }}
        </v-btn>
        <v-spacer />
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          :label="$t('common.search')"
          single-line
          hide-details
          density="compact"
          variant="outlined"
          style="max-width: 250px"
        />
      </v-col>
    </v-row>

    <!-- Summary Stats -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="primary">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ partOpportunities.length }}</div>
            <div class="text-caption">{{ $t('admin.totalParts') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="info">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ averageOpportunities }}</div>
            <div class="text-caption">{{ $t('admin.avgOpportunities') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="success">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ minOpportunities }}</div>
            <div class="text-caption">{{ $t('admin.minOpportunities') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="warning">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ maxOpportunities }}</div>
            <div class="text-caption">{{ $t('admin.maxOpportunities') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Part Opportunities Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-data-table
            :headers="headers"
            :items="partOpportunities"
            :search="search"
            :loading="loading"
            :items-per-page="15"
            class="elevation-0"
          >
            <template v-slot:item.part_number="{ item }">
              <span class="font-weight-medium text-primary">{{ item.part_number }}</span>
            </template>

            <template v-slot:item.opportunities_per_unit="{ item }">
              <v-chip
                :color="getOpportunityColor(item.opportunities_per_unit)"
                size="small"
              >
                {{ item.opportunities_per_unit }}
              </v-chip>
            </template>

            <template v-slot:item.complexity="{ item }">
              <v-chip
                :color="getComplexityColor(item.complexity)"
                size="small"
                variant="tonal"
              >
                {{ item.complexity || $t('common.standard') }}
              </v-chip>
            </template>

            <template v-slot:item.is_active="{ item }">
              <v-icon :color="item.is_active !== false ? 'success' : 'grey'">
                {{ item.is_active !== false ? 'mdi-check-circle' : 'mdi-close-circle' }}
              </v-icon>
            </template>

            <template v-slot:item.actions="{ item }">
              <v-btn
                icon="mdi-pencil"
                size="small"
                variant="text"
                color="primary"
                @click="openEditDialog(item)"
              />
              <v-btn
                icon="mdi-delete"
                size="small"
                variant="text"
                color="error"
                @click="confirmDelete(item)"
              />
            </template>

            <template v-slot:no-data>
              <div class="text-center pa-4">
                <v-icon size="48" color="grey">mdi-chart-scatter-plot</v-icon>
                <p class="mt-2 text-grey">{{ $t('admin.noPartOpportunities') }}</p>
                <v-btn color="primary" class="mt-2" @click="openCreateDialog">
                  {{ $t('admin.addPartOpportunity') }}
                </v-btn>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="editDialog" max-width="600" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">{{ isEditing ? 'mdi-pencil' : 'mdi-plus' }}</v-icon>
          {{ isEditing ? $t('admin.editPartOpportunity') : $t('admin.addPartOpportunity') }}
        </v-card-title>
        <v-card-text>
          <v-form ref="form" v-model="formValid">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.part_number"
                  :label="$t('jobs.partNumber') + ' *'"
                  :rules="[rules.required, rules.maxLength50]"
                  variant="outlined"
                  density="comfortable"
                  :disabled="isEditing"
                  hint="e.g., PART-001, SKU-12345"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.opportunities_per_unit"
                  :label="$t('admin.opportunitiesPerUnit') + ' *'"
                  type="number"
                  :rules="[rules.required, rules.positive]"
                  variant="outlined"
                  density="comfortable"
                  :hint="$t('admin.opportunitiesHint')"
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.part_description"
                  :label="$t('admin.partDescription')"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="formData.complexity"
                  :items="complexityOptions"
                  :label="$t('admin.complexity')"
                  variant="outlined"
                  density="comfortable"
                  clearable
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-select
                  v-model="formData.client_id"
                  :items="clientOptions"
                  item-title="client_name"
                  item-value="client_id"
                  :label="$t('filters.client')"
                  variant="outlined"
                  density="comfortable"
                  :disabled="isEditing"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-textarea
                  v-model="formData.notes"
                  :label="$t('production.notes')"
                  variant="outlined"
                  density="comfortable"
                  rows="2"
                />
              </v-col>
            </v-row>
            <v-row v-if="isEditing">
              <v-col cols="12">
                <v-switch
                  v-model="formData.is_active"
                  :label="$t('common.active')"
                  color="success"
                  hide-details
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeEditDialog">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!formValid"
            @click="savePartOpportunity"
          >
            {{ isEditing ? $t('common.update') : $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Upload CSV Dialog -->
    <v-dialog v-model="uploadDialog" max-width="500" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-upload</v-icon>
          {{ $t('csv.uploadPartOpportunities') }}
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            {{ $t('csv.partOpportunitiesInfo') }}
          </v-alert>
          <v-file-input
            v-model="uploadFile"
            :label="$t('csv.selectFile')"
            accept=".csv"
            prepend-icon="mdi-file-delimited"
            variant="outlined"
            show-size
          />
          <v-checkbox
            v-model="replaceExisting"
            :label="$t('csv.replaceExisting')"
            :hint="$t('csv.replaceExistingHint')"
            persistent-hint
            color="warning"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeUploadDialog">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="uploading"
            :disabled="!uploadFile"
            @click="uploadCSV"
          >
            {{ $t('csv.upload') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">
          <v-icon class="mr-2">mdi-alert</v-icon>
          {{ $t('common.confirmDelete') }}
        </v-card-title>
        <v-card-text>
          {{ $t('admin.deletePartOpportunityConfirm', { part: deleteTarget?.part_number }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="error" :loading="deleting" @click="deletePartOpportunity">
            {{ $t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- How-to Guide Dialog -->
    <v-dialog v-model="showGuide" max-width="900" scrollable>
      <v-card>
        <v-card-title class="bg-purple text-white d-flex justify-space-between">
          <div class="d-flex align-center">
            <v-icon class="mr-2">mdi-help-circle</v-icon>
            Part Opportunities Guide
          </div>
          <v-btn icon variant="text" color="white" @click="showGuide = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>

        <v-card-text class="pa-0">
          <v-tabs v-model="guideTab" color="purple" grow>
            <v-tab value="overview">Overview</v-tab>
            <v-tab value="dpmo">DPMO Calculation</v-tab>
            <v-tab value="howto">How To Use</v-tab>
            <v-tab value="examples">Examples</v-tab>
          </v-tabs>

          <v-tabs-window v-model="guideTab" class="pa-4">
            <!-- Overview Tab -->
            <v-tabs-window-item value="overview">
              <v-alert type="info" variant="tonal" class="mb-4">
                <strong>What are Part Opportunities?</strong><br>
                Part Opportunities represent the number of potential defect points per unit of a product. This is a critical input for calculating DPMO (Defects Per Million Opportunities), a key Six Sigma quality metric.
              </v-alert>

              <h4 class="mb-3">Why Part Opportunities Matter</h4>
              <v-list density="compact">
                <v-list-item prepend-icon="mdi-target">
                  <v-list-item-title><strong>Quality Measurement</strong></v-list-item-title>
                  <v-list-item-subtitle>Enable accurate DPMO calculation for Six Sigma analysis</v-list-item-subtitle>
                </v-list-item>
                <v-list-item prepend-icon="mdi-compare">
                  <v-list-item-title><strong>Fair Comparison</strong></v-list-item-title>
                  <v-list-item-subtitle>Compare quality across products with different complexity levels</v-list-item-subtitle>
                </v-list-item>
                <v-list-item prepend-icon="mdi-chart-line">
                  <v-list-item-title><strong>Sigma Level</strong></v-list-item-title>
                  <v-list-item-subtitle>Calculate process sigma level (1σ to 6σ)</v-list-item-subtitle>
                </v-list-item>
              </v-list>

              <v-divider class="my-4" />

              <h4 class="mb-3">Summary Cards Explained</h4>
              <v-row>
                <v-col cols="6" md="3">
                  <v-card variant="tonal" color="primary" class="text-center pa-2">
                    <v-icon>mdi-counter</v-icon>
                    <div class="text-caption">Total Parts</div>
                    <div class="text-body-2">Number of part definitions</div>
                  </v-card>
                </v-col>
                <v-col cols="6" md="3">
                  <v-card variant="tonal" color="info" class="text-center pa-2">
                    <v-icon>mdi-calculator</v-icon>
                    <div class="text-caption">Avg Opportunities</div>
                    <div class="text-body-2">Average defect points per unit</div>
                  </v-card>
                </v-col>
                <v-col cols="6" md="3">
                  <v-card variant="tonal" color="success" class="text-center pa-2">
                    <v-icon>mdi-arrow-down</v-icon>
                    <div class="text-caption">Min Opportunities</div>
                    <div class="text-body-2">Simplest product</div>
                  </v-card>
                </v-col>
                <v-col cols="6" md="3">
                  <v-card variant="tonal" color="warning" class="text-center pa-2">
                    <v-icon>mdi-arrow-up</v-icon>
                    <div class="text-caption">Max Opportunities</div>
                    <div class="text-body-2">Most complex product</div>
                  </v-card>
                </v-col>
              </v-row>
            </v-tabs-window-item>

            <!-- DPMO Calculation Tab -->
            <v-tabs-window-item value="dpmo">
              <h4 class="mb-3">Understanding DPMO</h4>
              <v-alert type="success" variant="tonal" class="mb-4">
                <strong>DPMO Formula:</strong><br>
                <code class="text-h6">DPMO = (Defects × 1,000,000) ÷ (Units × Opportunities per Unit)</code>
              </v-alert>

              <h4 class="mb-3">Example Calculation</h4>
              <v-card variant="outlined" class="mb-4 pa-4">
                <v-row>
                  <v-col cols="12" md="6">
                    <p><strong>Given:</strong></p>
                    <ul>
                      <li>Units produced: 1,000</li>
                      <li>Defects found: 15</li>
                      <li>Opportunities per unit: 20</li>
                    </ul>
                  </v-col>
                  <v-col cols="12" md="6">
                    <p><strong>Calculation:</strong></p>
                    <p>Total opportunities = 1,000 × 20 = 20,000</p>
                    <p>DPMO = (15 × 1,000,000) ÷ 20,000</p>
                    <p class="text-h6 text-primary">DPMO = 750</p>
                  </v-col>
                </v-row>
              </v-card>

              <h4 class="mb-3">Sigma Level Reference</h4>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>Sigma Level</th>
                    <th>DPMO</th>
                    <th>Yield %</th>
                    <th>Rating</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>6σ</td>
                    <td>3.4</td>
                    <td>99.99966%</td>
                    <td><v-chip size="small" color="success">World Class</v-chip></td>
                  </tr>
                  <tr>
                    <td>5σ</td>
                    <td>233</td>
                    <td>99.977%</td>
                    <td><v-chip size="small" color="success">Excellent</v-chip></td>
                  </tr>
                  <tr>
                    <td>4σ</td>
                    <td>6,210</td>
                    <td>99.379%</td>
                    <td><v-chip size="small" color="info">Good</v-chip></td>
                  </tr>
                  <tr>
                    <td>3σ</td>
                    <td>66,807</td>
                    <td>93.32%</td>
                    <td><v-chip size="small" color="warning">Average</v-chip></td>
                  </tr>
                  <tr>
                    <td>2σ</td>
                    <td>308,538</td>
                    <td>69.15%</td>
                    <td><v-chip size="small" color="error">Poor</v-chip></td>
                  </tr>
                </tbody>
              </v-table>

              <v-alert type="warning" variant="tonal" class="mt-4">
                <strong>Important:</strong> Accurate opportunity counts are essential for meaningful DPMO calculations. Underestimating opportunities inflates DPMO, while overestimating deflates it.
              </v-alert>
            </v-tabs-window-item>

            <!-- How To Use Tab -->
            <v-tabs-window-item value="howto">
              <h4 class="mb-3">Adding a New Part</h4>
              <v-stepper :items="['Click Add', 'Fill Form', 'Save']" alt-labels class="elevation-0 mb-4">
                <template v-slot:item.1>
                  <v-card flat>
                    <v-card-text>
                      <p>Click the <v-btn size="x-small" color="primary"><v-icon size="x-small">mdi-plus</v-icon> Add Part Opportunity</v-btn> button</p>
                    </v-card-text>
                  </v-card>
                </template>
                <template v-slot:item.2>
                  <v-card flat>
                    <v-card-text>
                      <ul>
                        <li><strong>Part Number:</strong> Unique identifier (e.g., SKU-001)</li>
                        <li><strong>Opportunities per Unit:</strong> Number of potential defect points</li>
                        <li><strong>Description:</strong> Brief description of the part</li>
                        <li><strong>Complexity:</strong> Simple, Standard, Complex, or Very Complex</li>
                      </ul>
                    </v-card-text>
                  </v-card>
                </template>
                <template v-slot:item.3>
                  <v-card flat>
                    <v-card-text>
                      <p>Review the data and click <strong>Save</strong></p>
                      <p>The part will now be available for quality calculations</p>
                    </v-card-text>
                  </v-card>
                </template>
              </v-stepper>

              <v-divider class="my-4" />

              <h4 class="mb-3">CSV Upload Format</h4>
              <v-alert type="info" variant="tonal" class="mb-3">
                Use CSV upload to import multiple parts at once. Click "Download Template" to get the correct format.
              </v-alert>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Required</th>
                    <th>Description</th>
                    <th>Example</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>part_number</td>
                    <td><v-icon color="success">mdi-check</v-icon></td>
                    <td>Unique part identifier</td>
                    <td>PART-001</td>
                  </tr>
                  <tr>
                    <td>opportunities_per_unit</td>
                    <td><v-icon color="success">mdi-check</v-icon></td>
                    <td>Number of defect opportunities</td>
                    <td>15</td>
                  </tr>
                  <tr>
                    <td>part_description</td>
                    <td><v-icon color="grey">mdi-minus</v-icon></td>
                    <td>Description text</td>
                    <td>Standard T-Shirt</td>
                  </tr>
                  <tr>
                    <td>complexity</td>
                    <td><v-icon color="grey">mdi-minus</v-icon></td>
                    <td>Simple/Standard/Complex/Very Complex</td>
                    <td>Standard</td>
                  </tr>
                  <tr>
                    <td>notes</td>
                    <td><v-icon color="grey">mdi-minus</v-icon></td>
                    <td>Additional notes</td>
                    <td>Basic garment</td>
                  </tr>
                </tbody>
              </v-table>

              <v-divider class="my-4" />

              <h4 class="mb-3">Determining Opportunity Count</h4>
              <p class="mb-3">Count all potential defect points in a product. Consider:</p>
              <ul>
                <li>Stitching/seam points</li>
                <li>Material quality checks</li>
                <li>Dimensional measurements</li>
                <li>Finishing operations</li>
                <li>Assembly points</li>
                <li>Labeling and tagging</li>
              </ul>
            </v-tabs-window-item>

            <!-- Examples Tab -->
            <v-tabs-window-item value="examples">
              <h4 class="mb-3">Industry Examples</h4>

              <v-expansion-panels>
                <v-expansion-panel title="Example: T-Shirt Manufacturing">
                  <v-expansion-panel-text>
                    <v-table density="compact">
                      <tbody>
                        <tr><td>Collar stitching</td><td>2 opportunities</td></tr>
                        <tr><td>Shoulder seams (2)</td><td>4 opportunities</td></tr>
                        <tr><td>Side seams (2)</td><td>4 opportunities</td></tr>
                        <tr><td>Sleeve attachment (2)</td><td>4 opportunities</td></tr>
                        <tr><td>Sleeve hem (2)</td><td>2 opportunities</td></tr>
                        <tr><td>Bottom hem</td><td>2 opportunities</td></tr>
                        <tr><td>Label attachment</td><td>1 opportunity</td></tr>
                        <tr><td>Print/decoration</td><td>3 opportunities</td></tr>
                        <tr class="font-weight-bold"><td>Total</td><td>22 opportunities</td></tr>
                      </tbody>
                    </v-table>
                  </v-expansion-panel-text>
                </v-expansion-panel>

                <v-expansion-panel title="Example: Boot Manufacturing">
                  <v-expansion-panel-text>
                    <v-table density="compact">
                      <tbody>
                        <tr><td>Upper stitching</td><td>8 opportunities</td></tr>
                        <tr><td>Sole attachment</td><td>4 opportunities</td></tr>
                        <tr><td>Heel attachment</td><td>2 opportunities</td></tr>
                        <tr><td>Lace holes (12)</td><td>12 opportunities</td></tr>
                        <tr><td>Tongue attachment</td><td>2 opportunities</td></tr>
                        <tr><td>Inner lining</td><td>4 opportunities</td></tr>
                        <tr><td>Logo/branding</td><td>2 opportunities</td></tr>
                        <tr><td>Finishing</td><td>3 opportunities</td></tr>
                        <tr class="font-weight-bold"><td>Total</td><td>37 opportunities</td></tr>
                      </tbody>
                    </v-table>
                  </v-expansion-panel-text>
                </v-expansion-panel>

                <v-expansion-panel title="Example: Simple Accessory (Belt)">
                  <v-expansion-panel-text>
                    <v-table density="compact">
                      <tbody>
                        <tr><td>Buckle attachment</td><td>2 opportunities</td></tr>
                        <tr><td>Strap material</td><td>2 opportunities</td></tr>
                        <tr><td>Stitching</td><td>2 opportunities</td></tr>
                        <tr><td>Holes (5)</td><td>5 opportunities</td></tr>
                        <tr><td>Edge finishing</td><td>2 opportunities</td></tr>
                        <tr class="font-weight-bold"><td>Total</td><td>13 opportunities</td></tr>
                      </tbody>
                    </v-table>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>

              <v-divider class="my-4" />

              <v-alert type="success" variant="tonal">
                <strong>Tip:</strong> Work with your quality team to establish consistent opportunity counting methods across all products. Document your counting methodology for consistency.
              </v-alert>
            </v-tabs-window-item>
          </v-tabs-window>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn color="purple" @click="showGuide = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar.show = false">{{ $t('common.close') }}</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const { t } = useI18n()

// State
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const deleting = ref(false)
const showGuide = ref(false)
const guideTab = ref('overview')
const clients = ref([])
const selectedClient = ref(null)
const partOpportunities = ref([])
const search = ref('')

// Dialogs
const editDialog = ref(false)
const uploadDialog = ref(false)
const deleteDialog = ref(false)
const isEditing = ref(false)
const deleteTarget = ref(null)

// Form
const form = ref(null)
const formValid = ref(false)
const formData = ref({
  part_number: '',
  opportunities_per_unit: 10,
  part_description: '',
  complexity: '',
  client_id: null,
  notes: '',
  is_active: true
})

// Upload
const uploadFile = ref(null)
const replaceExisting = ref(false)

// Snackbar
const snackbar = ref({
  show: false,
  message: '',
  color: 'success'
})

// Options
const complexityOptions = ['Simple', 'Standard', 'Complex', 'Very Complex']

// Validation rules
const rules = {
  required: v => !!v || t('validation.required'),
  maxLength50: v => !v || v.length <= 50 || t('validation.maxLength', { max: 50 }),
  positive: v => (v && v > 0) || t('validation.positive')
}

// Computed
const clientOptions = computed(() => {
  return [{ client_id: null, client_name: t('common.all') }, ...clients.value]
})

const averageOpportunities = computed(() => {
  if (partOpportunities.value.length === 0) return 0
  const sum = partOpportunities.value.reduce((acc, p) => acc + (p.opportunities_per_unit || 0), 0)
  return Math.round(sum / partOpportunities.value.length)
})

const minOpportunities = computed(() => {
  if (partOpportunities.value.length === 0) return 0
  return Math.min(...partOpportunities.value.map(p => p.opportunities_per_unit || 0))
})

const maxOpportunities = computed(() => {
  if (partOpportunities.value.length === 0) return 0
  return Math.max(...partOpportunities.value.map(p => p.opportunities_per_unit || 0))
})

const headers = computed(() => [
  { title: t('jobs.partNumber'), key: 'part_number', sortable: true },
  { title: t('admin.partDescription'), key: 'part_description', sortable: true },
  { title: t('admin.opportunitiesPerUnit'), key: 'opportunities_per_unit', sortable: true },
  { title: t('admin.complexity'), key: 'complexity', sortable: true },
  { title: t('common.active'), key: 'is_active', sortable: true },
  { title: t('common.actions'), key: 'actions', sortable: false, align: 'end' }
])

// Methods
const getOpportunityColor = (count) => {
  if (count <= 5) return 'success'
  if (count <= 15) return 'info'
  if (count <= 30) return 'warning'
  return 'error'
}

const getComplexityColor = (complexity) => {
  switch (complexity) {
    case 'Simple': return 'success'
    case 'Standard': return 'info'
    case 'Complex': return 'warning'
    case 'Very Complex': return 'error'
    default: return 'grey'
  }
}

const loadClients = async () => {
  try {
    const res = await api.getClients()
    clients.value = res.data || []
  } catch (error) {
    showSnackbar(t('errors.general'), 'error')
  }
}

const loadPartOpportunities = async () => {
  loading.value = true
  try {
    const params = {}
    if (selectedClient.value) {
      params.client_id = selectedClient.value
    }
    const res = await api.get('/part-opportunities', { params })
    partOpportunities.value = res.data || []
  } catch (error) {
    console.error('Failed to load part opportunities:', error)
    partOpportunities.value = []
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  isEditing.value = false
  formData.value = {
    part_number: '',
    opportunities_per_unit: 10,
    part_description: '',
    complexity: 'Standard',
    client_id: selectedClient.value,
    notes: '',
    is_active: true
  }
  editDialog.value = true
}

const openEditDialog = (item) => {
  isEditing.value = true
  formData.value = { ...item }
  editDialog.value = true
}

const closeEditDialog = () => {
  editDialog.value = false
  form.value?.reset()
}

const savePartOpportunity = async () => {
  if (!formValid.value) return

  saving.value = true
  try {
    if (isEditing.value) {
      await api.put(`/part-opportunities/${formData.value.part_opportunities_id}`, formData.value)
      showSnackbar(t('success.updated'), 'success')
    } else {
      await api.post('/part-opportunities', formData.value)
      showSnackbar(t('success.saved'), 'success')
    }
    closeEditDialog()
    await loadPartOpportunities()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
  } finally {
    saving.value = false
  }
}

const confirmDelete = (item) => {
  deleteTarget.value = item
  deleteDialog.value = true
}

const deletePartOpportunity = async () => {
  if (!deleteTarget.value) return

  deleting.value = true
  try {
    await api.delete(`/part-opportunities/${deleteTarget.value.part_opportunities_id}`)
    showSnackbar(t('success.deleted'), 'success')
    deleteDialog.value = false
    await loadPartOpportunities()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
  } finally {
    deleting.value = false
  }
}

const openUploadDialog = () => {
  uploadFile.value = null
  replaceExisting.value = false
  uploadDialog.value = true
}

const closeUploadDialog = () => {
  uploadDialog.value = false
  uploadFile.value = null
}

const uploadCSV = async () => {
  if (!uploadFile.value) return

  uploading.value = true
  try {
    const formDataUpload = new FormData()
    formDataUpload.append('file', uploadFile.value)
    formDataUpload.append('replace_existing', replaceExisting.value)
    if (selectedClient.value) {
      formDataUpload.append('client_id', selectedClient.value)
    }

    const res = await api.post('/part-opportunities/upload', formDataUpload, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    showSnackbar(t('csv.success', { count: res.data.created || 0 }), 'success')
    closeUploadDialog()
    await loadPartOpportunities()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('csv.error'), 'error')
  } finally {
    uploading.value = false
  }
}

const downloadTemplate = () => {
  const headers = ['part_number', 'opportunities_per_unit', 'part_description', 'complexity', 'notes']
  const example = ['PART-001', '15', 'Standard T-Shirt', 'Standard', 'Basic garment']
  const csv = [headers.join(','), example.join(',')].join('\n')

  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'part_opportunities_template.csv'
  a.click()
  URL.revokeObjectURL(url)

  showSnackbar(t('success.downloaded'), 'success')
}

const showSnackbar = (message, color = 'success') => {
  snackbar.value = { show: true, message, color }
}

onMounted(() => {
  loadClients()
  loadPartOpportunities()
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
